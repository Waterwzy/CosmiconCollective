from __future__ import annotations

import asyncio
import json
import os
import random
import time
from dataclasses import dataclass
from typing import Any, Literal

import httpx
from loguru import logger

from .context import GameView
from .player.dice import Dice
from .player.effects import Effect
from .player.helper import Select
from .player.player import Player, random_select

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}

_GAME_RULES = """【游戏规则】
- 每回合双方交换攻守；第一轮随机决定攻守。
- 攻击方先选骰，有 2 次重投机会；防御方后选骰，无重投机会（可能受效果影响）。
- 结算：攻击方点数（已选骰子点数之和 + 额外加成）与防御方点数（已选骰子点数之和 + 额外加成）相减，差值（不小于 0）即攻击方对防御方造成的伤害。
- 一方血量降至 0 即失败。
- 骰子分普通骰（可掷出 1~面数）与曜彩骰（6 个固定面，每面有固定点数与效果）。
- 效果可附着于角色，由技能或骰子触发，可能影响点数、伤害、血量、重投次数等。"""

_SYSTEM_PROMPT = (
    "你是《银河战力党》的 AI 玩家。这是一个回合制骰子对战游戏。\n\n"
    + _GAME_RULES
    + "\n\n【你的任务】\n在每个选择阶段，从当前可用骰子中做出一次选择，以最大化自己的胜率。\n\n"
    "【输出规范】\n你必须且只能输出一个 JSON 对象，格式如下：\n"
    '{"action": <1|2|3>, "selected": [<骰子下标>, ...]}\n'
    "- action=1：确认，selected 为最终选定的骰子下标列表（数量需符合要求）。\n"
    "- action=2：重投，selected 为重投的骰子下标列表（消耗 1 次重投机会，需有剩余重投次数）。\n"
    "- action=3：使用曜彩骰（selected 为空数组 []，不消耗重投次数；场上已有曜彩骰时不能再次使用）。\n\n"
    "根据直觉快速选择，不要进行思考、不要输出推理过程。\n"
    "只输出 JSON，不要输出任何其他文字或解释。"
)

_SELECT_SYSTEM_PROMPT = (
    "你是《银河战力党》的 AI 玩家，请根据角色描述选择一个你想使用的角色。"
)

_SPECIAL_DICE_SYSTEM_PROMPT = (
    "你是《银河战力党》的 AI 玩家，请根据你的角色技能选择一个曜彩骰。\n\n" + _GAME_RULES
)


class _RetryableHTTPError(Exception):
    """可重试的 HTTP 状态（429/5xx）。"""


@dataclass
class LLMEndpoint:
    base_url: str
    api_key: str = ""
    model: str = ""


class LLMClient:
    """原生异步的 OpenAI 兼容聊天客户端：自动端点回退 + 指数重试。

    配置来源（优先级从高到低）：构造函数参数 > 环境变量 > 项目根目录 .env 文件。
    LLM_BASE_URLS / LLM_API_KEYS / LLM_MODELS 均可用逗号分隔多个以支持回退。
    """

    def __init__(
        self,
        endpoints: list[LLMEndpoint] | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        backoff_base: float | None = None,
    ) -> None:
        self.endpoints = endpoints if endpoints is not None else _endpoints_from_env()
        self.timeout = (
            timeout if timeout is not None else _env_float("LLM_TIMEOUT", 60.0)
        )
        self.max_retries = (
            max_retries if max_retries is not None else _env_int("LLM_MAX_RETRIES", 3)
        )
        self.backoff_base = (
            backoff_base
            if backoff_base is not None
            else _env_float("LLM_BACKOFF_BASE", 1.0)
        )

    async def chat(
        self, messages: list[dict[str, str]], json_mode: bool = False
    ) -> str:
        """依次尝试各端点，某端点失败则回退到下一个；全部失败抛出 RuntimeError。"""
        if not self.endpoints:
            raise RuntimeError(
                "未配置任何 LLM 端点（请设置 LLM_BASE_URLS / LLM_API_KEYS / LLM_MODELS）"
            )
        last_error: Exception | None = None
        for endpoint in self.endpoints:
            try:
                return await self._chat_one(endpoint, messages, json_mode)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    f"LLM 端点失败，回退到下一个 | 端点={endpoint.base_url} 错误={exc}"
                )
                last_error = exc
        raise RuntimeError(f"所有 LLM 端点均调用失败：{last_error}")

    async def _chat_one(
        self, endpoint: LLMEndpoint, messages: list[dict[str, str]], json_mode: bool
    ) -> str:
        url = endpoint.base_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if endpoint.api_key:
            headers["Authorization"] = f"Bearer {endpoint.api_key}"
        payload: dict[str, Any] = {
            "model": endpoint.model,
            "messages": messages,
            "reasoning_effort": "low",
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        prompt_chars = sum(len(msg["content"]) for msg in messages)
        logger.info(
            f"LLM 请求 | 端点={endpoint.base_url} 模型={endpoint.model} "
            f"消息数={len(messages)} 提示词={prompt_chars}字符 超时={self.timeout}s"
        )
        logger.debug(f"LLM 请求体 | {json.dumps(payload, ensure_ascii=False)}")

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            started = time.perf_counter()
            # 1) 传输层错误
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(url, json=payload, headers=headers)
            except httpx.HTTPError as exc:
                elapsed = time.perf_counter() - started
                logger.warning(
                    f"LLM 传输错误 | 端点={url} 第{attempt + 1}次 "
                    f"耗时={elapsed:.2f}s 错误={exc}"
                )
                last_error = exc
                if attempt == self.max_retries - 1:
                    break
                delay = self.backoff_base * (2**attempt)
                logger.warning(f"LLM 重试等待 {delay:.2f}s")
                await asyncio.sleep(delay)
                continue

            elapsed = time.perf_counter() - started
            logger.info(
                f"LLM 响应 | 端点={url} 状态={resp.status_code} "
                f"耗时={elapsed:.2f}s 返回体={len(resp.text)}字符"
            )
            logger.info(f"LLM 原始返回体 | {resp.text}")

            # 2) 可重试状态码
            if resp.status_code in _RETRYABLE_STATUS:
                last_error = RuntimeError(f"HTTP {resp.status_code}")
                if attempt == self.max_retries - 1:
                    break
                delay = self.backoff_base * (2**attempt)
                logger.warning(f"LLM 状态 {resp.status_code} 可重试，等待 {delay:.2f}s")
                await asyncio.sleep(delay)
                continue

            # 3) 其余 4xx：不重试，直接抛出交给上层回退端点
            if resp.status_code >= 400:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")

            # 4) 解析响应
            try:
                data = resp.json()
                choices = data.get("choices") or []
                if not choices:
                    raise RuntimeError("响应缺少 choices 字段")
                content = choices[0]["message"]["content"]
                if not isinstance(content, str):
                    raise TypeError("响应内容不是字符串")
                return content
            except (ValueError, KeyError, TypeError, RuntimeError) as exc:
                last_error = exc
                if attempt == self.max_retries - 1:
                    break
                delay = self.backoff_base * (2**attempt)
                logger.warning(f"LLM 响应解析失败，等待 {delay:.2f}s 重试：{exc}")
                await asyncio.sleep(delay)
                continue

        raise RuntimeError(
            f"端点 {endpoint.base_url} 调用失败（重试 {self.max_retries} 次）：{last_error}"
        )


class AIAgent:
    """管理单个 AI 玩家的决策：选角 / 选曜彩骰 / 选骰，返回值与真人玩家一致。"""

    def __init__(
        self,
        player: Player | None = None,
        client: LLMClient | None = None,
        *,
        max_illegal_retries: int = 3,
    ) -> None:
        self.player = player
        self.client = client if client is not None else LLMClient()
        self.max_illegal_retries = max_illegal_retries

    # ---- 对外同步决策入口 ----

    def decide(
        self,
        role: Literal["attack", "defence"],
        reload_times: int,
        view: GameView,
        rng: random.Random | None = None,
    ) -> tuple[int, list]:
        """返回 (action, selected)，与真人 select_dice 一致；内部复用 _legal_select 校验。"""
        assert self.player is not None, "AIAgent 未绑定玩家"
        messages: list[dict[str, str]] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": self._build_user_prompt(role, reload_times, view),
            },
        ]
        for _ in range(self.max_illegal_retries + 1):
            try:
                raw = self._call(messages)
            except Exception:  # noqa: BLE001
                return random_select(self.player, role, rng)
            try:
                action, selected = self._parse_decision(raw)
            except (ValueError, KeyError, TypeError):
                action, selected = -1, []
            if self.player._legal_select(selected, action, role, reload_times, view):
                return action, selected
            messages.append({"role": "assistant", "content": raw})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"你的上一次输出不合法。{self._describe_error(action, selected, role, reload_times, view)}"
                        "请重新输出合法 JSON。"
                    ),
                }
            )
        return random_select(self.player, role, rng)

    def select_character(self, candidates: list[Player]) -> Player:
        """LLM 独立选角（prompt 不含玩家选择）。返回选中的角色实例，由调用方 deepcopy 隔离。"""
        menu = "\n".join(
            f"{i}. {player.create_description()}" for i, player in enumerate(candidates)
        )
        messages: list[dict[str, str]] = [
            {"role": "system", "content": _SELECT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"可选角色（下标: 描述）：\n{menu}\n\n"
                    '请只输出 JSON：{"choice": <下标>}'
                ),
            },
        ]
        for _ in range(self.max_illegal_retries + 1):
            try:
                raw = self._call(messages)
            except Exception:  # noqa: BLE001
                break
            index = self._try_parse_choice(raw, len(candidates))
            if index is not None:
                return candidates[index]
            messages.append({"role": "assistant", "content": raw})
            messages.append(
                {
                    "role": "user",
                    "content": f"无效选择，请输出 0~{len(candidates) - 1} 的合法 JSON。",
                }
            )
        return candidates[random.randrange(len(candidates))]

    def select_special_dice(self, candidates: list[Dice]) -> Dice:
        """LLM 独立选曜彩骰。返回选中的骰子实例，由调用方 deepcopy 隔离。"""
        menu = "\n\n".join(
            f"{i}. {dice.create_description()}" for i, dice in enumerate(candidates)
        )
        user_lines: list[str] = []
        if self.player is not None:
            user_lines.append("你的角色：")
            user_lines.append(self.player.create_description())
            user_lines.append("")
        user_lines.append(f"可选曜彩骰（下标: 描述）：\n{menu}")
        user_lines.append(
            '请根据你的角色技能选择最合适的曜彩骰，只输出 JSON：{"choice": <下标>}'
        )
        messages: list[dict[str, str]] = [
            {"role": "system", "content": _SPECIAL_DICE_SYSTEM_PROMPT},
            {"role": "user", "content": "\n".join(user_lines)},
        ]
        for _ in range(self.max_illegal_retries + 1):
            try:
                raw = self._call(messages)
            except Exception:  # noqa: BLE001
                break
            index = self._try_parse_choice(raw, len(candidates))
            if index is not None:
                return candidates[index]
            messages.append({"role": "assistant", "content": raw})
            messages.append(
                {
                    "role": "user",
                    "content": f"无效选择，请输出 0~{len(candidates) - 1} 的合法 JSON。",
                }
            )
        return candidates[random.randrange(len(candidates))]

    # ---- 内部实现 ----

    def _call(self, messages: list[dict[str, str]]) -> str:
        """同步桥接：在游戏线程里用 asyncio.run 调用异步 LLM 客户端。"""
        started = time.perf_counter()
        result = asyncio.run(self.client.chat(messages, json_mode=True))
        logger.info(f"LLM 调用完成 | 总耗时={time.perf_counter() - started:.2f}s")
        return result

    def _build_user_prompt(
        self, role: Literal["attack", "defence"], reload_times: int, view: GameView
    ) -> str:
        assert self.player is not None
        me = view.attacker if self.player.role == "attacker" else view.defender
        opp = view.defender if self.player.role == "attacker" else view.attacker
        phase = "攻击" if role == "attack" else "防御"
        need = self.player.attack_dice if role == "attack" else self.player.defence_dice

        lines: list[str] = []
        lines.append(
            f"第 {view.round} 回合，你是{'攻击方' if self.player.role == 'attacker' else '防御方'}，"
            f"当前处于{phase}阶段。"
        )
        lines.append(f"你需选择骰子数量：{need}；剩余重投次数：{reload_times}。")
        lines.append("")
        lines.append("【我方角色】")
        lines.append(me.create_description(effect_names_only=True))
        lines.append(f"当前血量：{me.hp}")
        lines.append("你当前已掷出的骰子（下标: 描述）：")
        for i, dice in enumerate(me.dices):
            tag = "（必须选择）" if dice.must_select else ""
            lines.append(f"{i}: {dice}{tag}")
        if me.special_dice is not None:
            special_in_pool = any(dice.special for dice in me.dices)
            usable = me.special_dice.can_use(view) and not special_in_pool
            status = "可使用" if usable else "不可使用"
            lines.append(
                f"我的曜彩骰（剩余使用次数 {self.player.use_spe_times}，当前{status}）：\n"
                f"{me.special_dice.create_description()}"
            )
            if special_in_pool:
                lines.append("注意：你场上已有曜彩骰，本阶段不能再使用 action=3。")
        else:
            lines.append("我的曜彩骰：无")
        lines.append(f"我方当前效果：{self._effects_text(me.effects)}")
        lines.append("")
        lines.append("【对方角色】")
        lines.append(
            opp.create_description(include_dice_combo=False, effect_names_only=True)
        )
        lines.append(f"对方当前血量：{opp.hp}")
        if self.player.role == "defender" and opp.selected_dice:
            values = [dice.now_value for dice in opp.selected_dice]
            lines.append(
                f"对方（攻击方）已选定的骰子点数：{values}（合计 {sum(values)}）"
            )
        if opp.special_dice is not None:
            lines.append(f"对方曜彩骰：\n{opp.special_dice.create_description()}")
        else:
            lines.append("对方曜彩骰：无")
        lines.append(f"对方当前效果：{self._effects_text(opp.effects)}")
        lines.append("")
        related = self._related_effects_section(me, opp)
        if related:
            lines.append(related)
            lines.append("")
        lines.append(
            '请根据直觉快速做出本次选择，只输出 JSON：{"action": 1|2|3, "selected": [下标...]}'
        )
        return "\n".join(lines)

    @staticmethod
    def _effects_text(effects) -> str:
        """场上效果只列名称（介绍统一放在【相关效果】）。"""
        alive = [effect for effect in effects if effect.alive]
        if not alive:
            return "无"
        parts = []
        for effect in alive:
            layer = f"（{effect.layer}层）" if effect.addable else ""
            parts.append(f"{effect.name}{layer}")
        return "；".join(parts)

    @staticmethod
    def _related_effects_section(me, opp) -> str:
        """汇总上下文中出现的所有效果（按类型去重），每个效果只介绍一次。"""
        effect_types: list[type[Effect]] = []
        seen: set[type[Effect]] = set()
        for cls in list(me.related_effects) + list(opp.related_effects):
            if cls not in seen:
                seen.add(cls)
                effect_types.append(cls)
        for effect in list(me.effects) + list(opp.effects):
            cls = type(effect)
            if cls not in seen:
                seen.add(cls)
                effect_types.append(cls)
        if not effect_types:
            return ""
        lines = ["【相关效果】"]
        for cls in effect_types:
            name = getattr(cls, "name", "") or ""
            desc = getattr(cls, "description", "") or ""
            lines.append(f"- {name}：{desc}")
        return "\n".join(lines)

    @staticmethod
    def _parse_decision(raw: str) -> tuple[int, list[int]]:
        data = _extract_json(raw)
        action = int(data["action"])
        selected = [int(i) for i in data.get("selected", [])]
        return action, selected

    @staticmethod
    def _try_parse_choice(raw: str, limit: int) -> int | None:
        """解析选角/选骰 JSON，返回合法下标；解析失败或越界返回 None。"""
        try:
            data = _extract_json(raw)
            index = int(data["choice"])
            if 0 <= index < limit:
                return index
        except (ValueError, KeyError, TypeError):
            return None
        return None

    def _describe_error(
        self,
        action: int,
        selected: list[int],
        role: Literal["attack", "defence"],
        reload_times: int,
        view: GameView,
    ) -> str:
        assert self.player is not None
        need = self.player.attack_dice if role == "attack" else self.player.defence_dice
        must = [i for i, dice in enumerate(self.player.dices) if dice.must_select]
        count = len(self.player.dices)
        reasons: list[str] = []
        if action not in (1, 2, 3):
            reasons.append(f"action 必须是 1/2/3，你给了 {action}")
        else:
            if action in (1, 2) and not selected:
                reasons.append("action 为 1 或 2 时 selected 不能为空")
            if action == 2 and reload_times <= 0:
                reasons.append("没有剩余重投次数，不能使用 action=2")
            if action == 3:
                if self.player.use_spe_times <= 0:
                    reasons.append("曜彩骰剩余使用次数为 0")
                elif not self.player.special_dice:
                    reasons.append("你没有曜彩骰")
                elif not self.player.special_dice.can_use(view):
                    reasons.append("曜彩骰当前不满足使用条件")
                elif any(dice.special for dice in self.player.dices):
                    reasons.append("场上已有曜彩骰，不能再使用 action=3")
            if len(selected) != len(set(selected)):
                reasons.append("selected 存在重复下标")
            for i in selected:
                if not 0 <= i < count:
                    reasons.append(f"下标 {i} 越界（可用下标 0~{count - 1}）")
            if action == 1:
                if must and any(i not in selected for i in must):
                    reasons.append(f"必须选择的下标 {must} 未全部包含")
                if need != Select.NO_LIMIT and len(selected) != need:
                    reasons.append(
                        f"action=1 时必须选择恰好 {need} 颗，你选了 {len(selected)} 颗"
                    )
        return "；".join(reasons) or "选择不合法"


def _extract_json(raw: str) -> dict:
    """从模型输出中提取 JSON 对象（容忍 ```json 代码块与前后缀文字）。"""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    data = json.loads(text)
    if not isinstance(data, dict):
        raise TypeError("JSON 顶层不是对象")
    return data


def _endpoints_from_env() -> list[LLMEndpoint]:
    urls = [
        s.strip() for s in os.environ.get("LLM_BASE_URLS", "").split(",") if s.strip()
    ]
    keys = [s.strip() for s in os.environ.get("LLM_API_KEYS", "").split(",")]
    models = [s.strip() for s in os.environ.get("LLM_MODELS", "").split(",")]
    endpoints: list[LLMEndpoint] = []
    for i, url in enumerate(urls):
        key = keys[i].strip() if i < len(keys) else (keys[-1].strip() if keys else "")
        model = (
            models[i].strip()
            if i < len(models)
            else (models[-1].strip() if models else "")
        )
        endpoints.append(LLMEndpoint(url, key, model))
    return endpoints


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _load_dotenv(path: str | None = None) -> None:
    """加载 .env 文件到环境变量（已存在的环境变量优先，不被覆盖）。"""
    dotenv_path = path or os.path.join(os.getcwd(), ".env")
    if not os.path.isfile(dotenv_path):
        return
    try:
        with open(dotenv_path, encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[7:].strip()
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
                    value = value[1:-1]
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        pass


_load_dotenv()

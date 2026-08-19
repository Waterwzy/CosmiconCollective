"""WebUI 对局会话：把命令行版 GameManager 包装成可被 WebSocket 驱动的交互式对局。

- 游戏逻辑在游戏线程中同步执行，人类玩家的输入通过 _DecisionBridge 阻塞等待前端提交；
- 游戏线程内的 print 输出通过按线程分流的 stdout 路由进入对局日志，推送给前端；
- 每个决策点都会向前端推送一次完整状态快照 + 增量日志。
"""

from __future__ import annotations

import copy
import sys
import threading
import traceback
from collections.abc import Callable
from typing import Any, Literal

from core.ai import AIAgent
from core.context import GamePatch
from core.player.default import players, special_dices
from core.player.helper import Select
from core.player.player import Player
from main import GameManager


class _SessionStopped(Exception):
    """前端断开或主动终止对局时，在游戏线程中抛出以结束游戏。"""


class _ThreadStdoutRouter:
    """按线程分流的 stdout 代理。

    游戏线程注册自己的日志 sink 后，其 print 进入对局日志；
    其他线程（如 uvicorn 主线程）的输出不受影响。
    """

    def __init__(self, real) -> None:
        self._real = real
        self._sinks: dict[int, _LogSink] = {}
        self._lock = threading.Lock()

    def register(self, sink: _LogSink) -> None:
        with self._lock:
            self._sinks[threading.get_ident()] = sink

    def unregister(self) -> None:
        with self._lock:
            self._sinks.pop(threading.get_ident(), None)

    def write(self, text: str) -> int:
        with self._lock:
            sink = self._sinks.get(threading.get_ident())
        if sink is not None:
            sink.write(text)
        else:
            self._real.write(text)
        return len(text)

    def flush(self) -> None:
        with self._lock:
            sink = self._sinks.get(threading.get_ident())
        if sink is not None:
            sink.flush()
        else:
            self._real.flush()


_router: _ThreadStdoutRouter | None = None


def _install_stdout_router() -> _ThreadStdoutRouter:
    global _router
    if _router is None and not isinstance(sys.stdout, _ThreadStdoutRouter):
        _router = _ThreadStdoutRouter(sys.stdout)
        sys.stdout = _router
    assert _router is not None
    return _router


class _LogSink:
    """收集游戏线程的 print 输出，按行缓冲，notify 时取走增量。"""

    def __init__(self) -> None:
        self._buf = ""
        self._lines: list[str] = []
        self._lock = threading.Lock()

    def write(self, text: str) -> None:
        with self._lock:
            self._buf += text
            while "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                if line:
                    self._lines.append(line)

    def flush(self) -> None:
        pass

    def drain(self) -> list[str]:
        with self._lock:
            lines = self._lines
            self._lines = []
            if self._buf:
                lines.append(self._buf)
                self._buf = ""
            return lines


def _dice_count(value: int | Select) -> int | str:
    return "any" if isinstance(value, Select) else value


def menu_payload() -> dict[str, Any]:
    """选角菜单：可选角色（排除 AI 角色）与曜彩骰列表。"""
    characters = []
    for index, player in enumerate(players):
        if player.is_agent:
            continue
        characters.append(
            {
                "index": index,
                "name": player.id,
                "hp": player.hp,
                "attack_dice": _dice_count(player.attack_dice),
                "defence_dice": _dice_count(player.defence_dice),
                "dices": [dice.sides for dice in player.dices],
                "description": player.description,
                "related_effects": [
                    {
                        "name": getattr(cls, "name", "") or "",
                        "description": getattr(cls, "description", "") or "",
                    }
                    for cls in player.related_effects
                ],
            }
        )
    dices = [
        {"index": index, "name": dice.name, "description": dice.create_description()}
        for index, dice in enumerate(special_dices)
    ]
    return {"type": "menu", "characters": characters, "special_dices": dices}


class _DecisionBridge:
    """挂到人类玩家 ai_agent 上的决策桥：把决策请求发给前端并阻塞等待回复。"""

    def __init__(self, session: GameSession) -> None:
        self.session = session
        self.player: Player | None = None

    def decide(
        self,
        role: Literal["attack", "defence"],
        reload_times: int,
        view,
        rng=None,
    ) -> tuple[int, list[int]]:
        session = self.session
        player = self.player
        assert player is not None
        while True:
            session.prompt = session.build_prompt(player, role, reload_times, view)
            session.notify()
            action, selected = session.wait_action()
            if player._legal_select(selected, action, role, reload_times, view):
                session.prompt = None
                return action, selected
            session.send_error("选择不合法，请检查所选骰子与操作后重试")


class GameSession:
    """一局人 vs LLM AI 的对局（对应命令行版 main.py 的 __main__ 流程）。"""

    def __init__(
        self,
        character_index: int,
        special_dice_index: int,
        seed: int | None = None,
        on_update: Callable[[dict], None] | None = None,
    ) -> None:
        if not (0 <= character_index < len(players)):
            raise ValueError("无效的角色下标")
        if players[character_index].is_agent:
            raise ValueError("该角色为 AI 角色，无法选择")
        if not (0 <= special_dice_index < len(special_dices)):
            raise ValueError("无效的曜彩骰下标")

        self._on_update = on_update
        self._action_event = threading.Event()
        self._stop_event = threading.Event()
        self._pending_action: tuple[int, list[int]] | None = None
        self.prompt: dict[str, Any] | None = None
        self.game_over_payload: dict[str, Any] | None = None
        self._sink: _LogSink | None = None
        self._thread: threading.Thread | None = None

        # deepcopy 隔离对局实例（模块级 players/special_dices 为共享模板）
        self.human = copy.deepcopy(players[character_index])
        self.human.special_dice = copy.deepcopy(special_dices[special_dice_index])
        bridge = _DecisionBridge(self)
        bridge.player = self.human
        self.human.ai_agent = bridge

        # AI 独立选角 + 选曜彩骰（与命令行版一致，LLM 失败时自动随机兜底）
        agent = AIAgent()
        ai_candidates = [p for p in players if p.id != "默认测试卡牌"]
        self.ai = copy.deepcopy(agent.select_character(ai_candidates))
        agent.player = self.ai
        self.ai.special_dice = copy.deepcopy(agent.select_special_dice(special_dices))
        self.ai.ai_agent = agent

        self.game = GameManager(self.human, self.ai, seed=seed)
        self._settlement: dict[str, Any] | None = None
        self._install_settlement_spy()

    # ---- 结算探针 ----

    def _install_settlement_spy(self) -> None:
        """包装对局实例的 apply_patch 与 next_round（不改动游戏核心代码）：

        - apply_patch：结算阶段（state == "sum"）出现普通伤害补丁时，捕获双方
          点数明细（骰面、骰子和、额外点数、乘数、总点数）与受击方前后血量；
        - next_round：一轮结算在此结束，立即推送一次更新（携带结算数据），
          让前端演出与 AI 的下轮决策并行，而不是等决策完才播出。
        """
        game = self.game
        original = game.context.apply_patch

        def spy(patch: GamePatch) -> None:
            if game.state == "sum":
                for dam in patch.damage:
                    if dam["type"] == "common":
                        if self._settlement is None:
                            self._settlement = self._capture_settlement()
                        self._settlement["hits"].append(dam["count"])
            original(patch)
            if self._settlement is not None and game.state == "sum":
                self._settlement["defender_hp_after"] = game.defender.hp

        game.context.apply_patch = spy  # type: ignore[method-assign]

        original_next_round = game.next_round

        def next_round_spy() -> None:
            original_next_round()
            if self._settlement is not None:
                self.notify()

        game.next_round = next_round_spy  # type: ignore[method-assign]

    def _capture_settlement(self) -> dict[str, Any]:
        game = self.game

        def side_info(player, dice_sum, extra, mult):
            return {
                "side": "you" if player is self.human else "opponent",
                "dices": [dice.now_value for dice in player.selected_dice],
                "dice_sum": dice_sum,
                "extra": extra,
                "mult": mult,
                "total": (dice_sum + extra) * mult,
            }

        return {
            "round": game.round,
            "attacker": side_info(
                game.attacker,
                game.attacker_sum,
                game.attacker_extra_sum,
                game.attacker_multiplier,
            ),
            "defender": side_info(
                game.defender,
                game.defender_sum,
                game.defender_extra_sum,
                game.defender_multiplier,
            ),
            "defender_hp_before": game.defender.hp,
            "defender_hp_after": game.defender.hp,
            "hits": [],
        }

    # ---- 生命周期 ----

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._action_event.set()

    def _run(self) -> None:
        router = _install_stdout_router()
        sink = _LogSink()
        self._sink = sink
        router.register(sink)
        try:
            assert self.human.special_dice is not None
            assert self.ai.special_dice is not None
            print(
                f"你选择了角色：{self.human.id}，曜彩骰：{self.human.special_dice.name}"
            )
            print(f"AI 选择了角色：{self.ai.id}，曜彩骰：{self.ai.special_dice.name}")
            self.game.main()
            self.game_over_payload = {"winner": self._winner(), "error": None}
        except _SessionStopped:
            self.game_over_payload = {"winner": None, "error": "对局已终止"}
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self.game_over_payload = {"winner": None, "error": f"对局异常结束：{exc}"}
        finally:
            router.unregister()
            self.prompt = None
            self.notify()

    def _winner(self) -> str:
        attacker, defender = self.game.attacker, self.game.defender
        if attacker.hp <= 0 and defender.hp <= 0:
            return "draw"
        winner = defender if attacker.hp <= 0 else attacker
        return "you" if winner is self.human else "opponent"

    # ---- 与前端交互 ----

    def notify(self) -> None:
        if self._on_update is not None:
            settlement, self._settlement = self._settlement, None
            self._on_update(
                {
                    "type": "update",
                    "log": self._sink.drain() if self._sink else [],
                    "state": self.serialize_state(),
                    "prompt": self.prompt,
                    "game_over": self.game_over_payload,
                    "settlement": settlement,
                }
            )

    def send_error(self, message: str) -> None:
        if self._on_update is not None:
            self._on_update({"type": "error", "message": message})

    def wait_action(self) -> tuple[int, list[int]]:
        while not self._stop_event.is_set():
            if self._action_event.wait(timeout=0.5):
                self._action_event.clear()
                if self._pending_action is not None:
                    action, self._pending_action = self._pending_action, None
                    return action
        raise _SessionStopped()

    def submit_action(self, action: int, selected: list[int]) -> bool:
        """前端提交决策。当前无待决策请求时返回 False。"""
        if self.prompt is None or self._stop_event.is_set():
            return False
        self._pending_action = (int(action), [int(i) for i in selected])
        self._action_event.set()
        return True

    # ---- 序列化 ----

    def build_prompt(
        self,
        player: Player,
        role: Literal["attack", "defence"],
        reload_times: int,
        view,
    ) -> dict[str, Any]:
        need = player.attack_dice if role == "attack" else player.defence_dice
        special = player.special_dice
        special_usable = bool(
            special is not None
            and player.use_spe_times > 0
            and not any(dice.special for dice in player.dices)
            and special.can_use(view)
        )
        return {
            "phase": role,
            "need": _dice_count(need),
            "reload_times": reload_times,
            "special_usable": special_usable,
        }

    def serialize_state(self) -> dict[str, Any]:
        game = self.game
        return {
            "round": game.round,
            "phase": game.state,
            "reload_times": game.reload_times,
            "attacker_sum": game.attacker_sum,
            "defender_sum": game.defender_sum,
            "attacker_extra_sum": game.attacker_extra_sum,
            "defender_extra_sum": game.defender_extra_sum,
            "attacker_multiplier": game.attacker_multiplier,
            "defender_multiplier": game.defender_multiplier,
            "you": self._serialize_player(self.human),
            "opponent": self._serialize_player(self.ai),
        }

    @staticmethod
    def _serialize_player(player: Player) -> dict[str, Any]:
        selected_ids = {id(dice) for dice in player.selected_dice}
        return {
            "name": player.id,
            "hp": player.hp,
            "max_hp": player.max_hp,
            "role": player.role,
            "attack_dice": _dice_count(player.attack_dice),
            "defence_dice": _dice_count(player.defence_dice),
            "dices": [
                {
                    "sides": dice.sides,
                    "value": dice.now_value,
                    "special": dice.special,
                    "must_select": dice.must_select,
                    "name": dice.name,
                    "effect": dice.now_effect.name if dice.now_effect else None,
                    "selected": id(dice) in selected_ids,
                }
                for dice in player.dices
            ],
            "effects": [
                {
                    "name": effect.name,
                    "layer": effect.layer,
                    "addable": effect.addable,
                    "description": getattr(type(effect), "description", "") or "",
                }
                for effect in player.effects
                if effect.alive
            ],
            "special_dice": (
                {
                    "name": player.special_dice.name,
                    "description": player.special_dice.create_description(),
                    "uses_left": player.use_spe_times,
                }
                if player.special_dice is not None
                else None
            ),
        }

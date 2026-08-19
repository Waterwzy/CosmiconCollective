"""AI 客户端与 AIAgent 的离线单元测试（不触网）。"""

import asyncio
import os
import random
from typing import ClassVar

import httpx
import pytest

from core.ai import AIAgent, LLMClient, LLMEndpoint, _extract_json
from core.player.default import (
    DefaultAIPlayer,
    DefaultPlayer,
    RealFate,
    RealRevenge,
    Strength,
    YellowSpringPlayer,
)
from core.player.player import random_select
from main import GameManager


class _FakeResponse:
    def __init__(self, status_code: int, content=None, text: str = ""):
        self.status_code = status_code
        self._content = content if content is not None else {}
        self.text = text

    def json(self):
        if isinstance(self._content, Exception):
            raise self._content
        return self._content


class _FakeAsyncClient:
    """每次实例化返回预设的响应序列。"""

    responses: ClassVar[list[_FakeResponse]] = []

    def __init__(self, timeout=None):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json=None, headers=None):
        resp = self.responses.pop(0)
        return resp


class _ScriptedClient:
    """按脚本顺序返回字符串（或异常）的假 LLM 客户端。"""

    def __init__(self, responses: list):
        self.responses = list(responses)
        self.calls: list[list[dict]] = []

    async def chat(self, messages, json_mode=False):
        self.calls.append(messages)
        resp = self.responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp


class _ConstantClient:
    """始终返回同一个响应的假 LLM 客户端。"""

    def __init__(self, response: str):
        self.response = response

    async def chat(self, messages, json_mode=False):
        return self.response


# ---- _extract_json ----


def test_extract_json_plain():
    assert _extract_json('{"action": 1, "selected": [0, 1]}') == {
        "action": 1,
        "selected": [0, 1],
    }


def test_extract_json_tolerates_fence_and_prose():
    raw = '好的，我的选择是：\n```json\n{"choice": 2}\n```\n以上。'
    assert _extract_json(raw) == {"choice": 2}


# ---- LLMClient ----


def test_llm_client_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.responses = [
        _FakeResponse(429),
        _FakeResponse(200, {"choices": [{"message": {"content": "ok"}}]}),
    ]
    client = LLMClient(
        endpoints=[LLMEndpoint("http://a.com/v1", "k", "m")],
        max_retries=3,
        backoff_base=0.001,
    )
    assert asyncio.run(client.chat([{"role": "user", "content": "hi"}])) == "ok"
    assert _FakeAsyncClient.responses == []  # 两次调用消耗完


def test_llm_client_falls_back_to_next_endpoint(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.responses = [
        _FakeResponse(500),  # 端点 a 失败
        _FakeResponse(500),
        _FakeResponse(
            200, {"choices": [{"message": {"content": "b-ok"}}]}
        ),  # 端点 b 成功
    ]
    client = LLMClient(
        endpoints=[
            LLMEndpoint("http://a.com/v1", "k", "m"),
            LLMEndpoint("http://b.com/v1", "k", "m"),
        ],
        max_retries=2,
        backoff_base=0.001,
    )
    assert asyncio.run(client.chat([{"role": "user", "content": "hi"}])) == "b-ok"


def test_llm_client_raises_when_all_fail(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.responses = [_FakeResponse(500)] * 4
    client = LLMClient(
        endpoints=[LLMEndpoint("http://a.com/v1", "k", "m")],
        max_retries=2,
        backoff_base=0.001,
    )
    with pytest.raises(RuntimeError):
        asyncio.run(client.chat([{"role": "user", "content": "hi"}]))


# ---- AIAgent.decide ----


def _make_game():
    return GameManager(DefaultPlayer(), DefaultAIPlayer(), seed=0)


def test_agent_decide_returns_valid_selection():
    game = _make_game()
    player = game.attacker
    agent = AIAgent(
        player=player, client=_ScriptedClient(['{"action": 1, "selected": [0, 1, 2]}'])
    )
    action, selected = agent.decide("attack", 2, game.context.create_view(), game.rng)
    assert action == 1
    assert selected == [0, 1, 2]


def test_agent_decide_retries_on_illegal_move():
    game = _make_game()
    player = game.attacker
    client = _ScriptedClient(
        ['{"action": 1, "selected": [0, 1]}', '{"action": 1, "selected": [0, 1, 2]}']
    )
    agent = AIAgent(player=player, client=client)
    action, selected = agent.decide("attack", 2, game.context.create_view(), game.rng)
    assert action == 1
    assert selected == [0, 1, 2]
    assert len(client.calls) == 2
    # 第二次请求应包含上一次的错误反馈（assistant + user 错误消息）
    second_messages = client.calls[1]
    assert any(msg["role"] == "assistant" for msg in second_messages)
    assert any(
        "不合法" in msg["content"] for msg in second_messages if msg["role"] == "user"
    )


def test_agent_decide_falls_back_to_random_on_llm_failure():
    game = _make_game()
    player = game.attacker
    agent = AIAgent(player=player, client=_ScriptedClient([RuntimeError("boom")]))
    action, selected = agent.decide("attack", 2, game.context.create_view(), game.rng)
    assert action == 1
    assert len(selected) == player.attack_dice
    assert player._legal_select(
        selected, action, "attack", 2, game.context.create_view()
    )


def test_agent_select_character_invalid_then_valid():
    from core.player.default import players

    candidates = [p for p in players if p.id != "默认测试卡牌"]
    agent = AIAgent(client=_ScriptedClient(['{"choice": 999}', '{"choice": 2}']))
    assert agent.select_character(candidates) is candidates[2]


def test_agent_select_special_dice():
    from core.player.default import special_dices

    agent = AIAgent(client=_ScriptedClient(['{"choice": 1}']))
    assert agent.select_special_dice(special_dices) is special_dices[1]


# ---- random_select ----


def test_random_select_respects_must_select():
    player = DefaultPlayer()
    player.dices[0].must_select = True
    rng = random.Random(0)
    action, selected = random_select(player, "attack", rng)
    assert action == 1
    assert 0 in selected
    assert len(selected) == player.attack_dice
    assert len(selected) == len(set(selected))


# ---- create_description ----


def test_player_create_description():
    desc = YellowSpringPlayer().create_description()
    assert "黄泉" in desc
    assert "无视" in desc  # 关联效果描述
    assert "33" in desc  # 最大生命值
    assert "初始攻击骰 2 颗" in desc


def test_special_dice_create_description():
    desc = RealFate().create_description()
    assert "真•命运" in desc
    assert "第1面" in desc and "第6面" in desc
    assert "必须选择" in desc
    assert "使用要求" in desc


def test_build_user_prompt_includes_special_dice_usage():
    game = GameManager(DefaultPlayer(), DefaultAIPlayer(), seed=0)
    player = game.attacker
    dice = RealRevenge()
    dice.master = player
    player.special_dice = dice
    agent = AIAgent(player=player, client=_ConstantClient("{}"))
    view = game.context.create_view()
    # 未满足条件（累计受伤 < 25）→ 不可使用
    assert "当前不可使用" in agent._build_user_prompt("attack", 2, view)
    assert "使用要求" in agent._build_user_prompt("attack", 2, view)
    # 满足条件 → 可使用
    player.total_damage_taken = 25
    assert "当前可使用" in agent._build_user_prompt("attack", 2, view)


def test_agent_select_special_dice_includes_character():
    from core.player.default import special_dices

    char = YellowSpringPlayer()
    client = _ScriptedClient(['{"choice": 1}'])
    agent = AIAgent(player=char, client=client)
    assert agent.select_special_dice(special_dices) is special_dices[1]
    user_content = client.calls[0][-1]["content"]
    assert "黄泉" in user_content
    assert "技能" in user_content


# ---- 集成：fake LLM 跑完整局 ----


def test_full_game_with_fake_llm_ai():
    """AI 玩家由 fake LLM 驱动，另一侧为随机 AI，验证整局可跑通并正常终局。"""
    ai_player = DefaultAIPlayer()
    agent = AIAgent(
        player=ai_player,
        client=_ConstantClient('{"action": 1, "selected": [0, 1, 2]}'),
    )
    ai_player.ai_agent = agent
    game = GameManager(ai_player, DefaultAIPlayer(), seed=0)
    game.main()
    assert game.attacker.hp <= 0 or game.defender.hp <= 0
    assert game.round <= 500


def test_deepcopy_player_isolates_instance():
    import copy

    player = YellowSpringPlayer()
    clone = copy.deepcopy(player)
    assert clone is not player
    assert clone.dices is not player.dices
    assert clone.dices[0] is not player.dices[0]
    clone.dices[0].now_value = 99
    clone.hp = 1
    assert player.dices[0].now_value == 0
    assert player.hp == player.max_hp


# ---- .env 加载 ----


def test_load_dotenv(monkeypatch, tmp_path):
    from core.ai import _load_dotenv

    env_file = tmp_path / ".env"
    env_file.write_text(
        'LLM_BASE_URLS="https://a.com/v1,https://b.com/v1"\n'
        "# 这是注释\n"
        "LLM_MODELS=gpt-4o,claude\n"
        "export LLM_TIMEOUT=10\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("LLM_BASE_URLS", raising=False)
    monkeypatch.delenv("LLM_MODELS", raising=False)
    monkeypatch.delenv("LLM_TIMEOUT", raising=False)
    _load_dotenv(str(env_file))
    assert os.environ["LLM_BASE_URLS"] == "https://a.com/v1,https://b.com/v1"
    assert os.environ["LLM_MODELS"] == "gpt-4o,claude"
    assert os.environ["LLM_TIMEOUT"] == "10"


def test_load_dotenv_does_not_override_existing(monkeypatch, tmp_path):
    from core.ai import _load_dotenv

    env_file = tmp_path / ".env"
    env_file.write_text("LLM_TIMEOUT=99\n", encoding="utf-8")
    monkeypatch.setenv("LLM_TIMEOUT", "42")
    _load_dotenv(str(env_file))
    assert os.environ["LLM_TIMEOUT"] == "42"


def test_prompt_does_not_leak_opponent_dice():
    """AI 只能看到自己已掷出的骰子，不能看到对手（尚未掷出的）骰子。"""
    game = GameManager(DefaultPlayer(), DefaultAIPlayer(), seed=0)
    player = game.attacker
    for dice in player.dices:
        dice.now_value = 88  # 己方骰子：唯一标记
    for dice in game.defender.dices:
        dice.now_value = 77  # 对方骰子：唯一标记
    agent = AIAgent(player=player, client=_ConstantClient("{}"))
    prompt = agent._build_user_prompt("attack", 2, game.context.create_view())
    assert "你当前已掷出的骰子" in prompt
    assert "根据直觉" in prompt
    assert "88" in prompt  # 己方骰子被展示
    assert "77" not in prompt  # 对方骰子点数不出现


def test_opponent_description_hides_dice_combo():
    """对敌方隐藏初始骰子配置（最大值）。"""
    game = GameManager(DefaultPlayer(), DefaultAIPlayer(), seed=0)
    opp_view = game.context.create_view().defender
    assert "初始骰子组合" in opp_view.create_description()
    assert "初始骰子组合" not in opp_view.create_description(include_dice_combo=False)


def test_defender_sees_attacker_selection():
    """AI 作为防御方时，应能看到攻击方已选定的骰子点数。"""
    game = GameManager(DefaultPlayer(), DefaultAIPlayer(), seed=0)
    defender = game.defender
    attacker = game.attacker
    attacker.selected_dice = list(attacker.dices[:3])
    for dice, value in zip(attacker.selected_dice, (5, 6, 8)):
        dice.now_value = value
    agent = AIAgent(player=defender, client=_ConstantClient("{}"))
    prompt = agent._build_user_prompt("defence", 0, game.context.create_view())
    assert "已选定的骰子点数" in prompt
    assert "[5, 6, 8]" in prompt
    assert "合计 19" in prompt


def test_prompt_dedupes_effects():
    """场景中效果只列名称，介绍统一在【相关效果】且每个效果只出现一次。"""
    game = GameManager(DefaultPlayer(), DefaultAIPlayer(), seed=0)
    player = game.attacker
    opp = game.defender
    player.effects.append(Strength(player, 3, False))
    opp.effects.append(Strength(opp, 2, False))
    agent = AIAgent(player=player, client=_ConstantClient("{}"))
    prompt = agent._build_user_prompt("attack", 2, game.context.create_view())
    # 场景中只列名称 + 层数，不列介绍
    assert "我方当前效果：力量（3层）" in prompt
    assert "对方当前效果：力量（2层）" in prompt
    # 介绍只出现在【相关效果】一次
    assert prompt.count("在攻击时，提供对应层数的攻击值加成") == 1
    assert "【相关效果】" in prompt
    assert "- 力量：在攻击时，提供对应层数的攻击值加成" in prompt


def test_select_special_dice_includes_game_rules():
    """选曜彩骰时注入基本玩法规则。"""
    from core.player.default import special_dices

    client = _ScriptedClient(['{"choice": 0}'])
    agent = AIAgent(player=YellowSpringPlayer(), client=client)
    agent.select_special_dice(special_dices)
    system_content = client.calls[0][0]["content"]
    assert "游戏规则" in system_content
    assert "攻击方先选骰" in system_content
    assert "曜彩骰" in system_content

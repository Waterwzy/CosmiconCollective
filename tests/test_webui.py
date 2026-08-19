"""WebUI 端到端冒烟测试：通过 WebSocket 完整打完一局（人 vs AI）。

LLM 端点被指向不可达地址并关闭重试，AI 会自动降级为随机决策，
人类玩家的决策由脚本自动提交（始终选择 action=1 确认）。
"""

import os

import pytest

pytest.importorskip("fastapi")

# 必须在导入 webui.server（进而导入 core.ai 读取 .env）之前设置，
# 使 LLM 调用快速失败并走随机兜底，保证测试速度。
os.environ["LLM_BASE_URLS"] = "http://127.0.0.1:9"
os.environ["LLM_API_KEYS"] = "test"
os.environ["LLM_MODELS"] = "test"
os.environ["LLM_MAX_RETRIES"] = "1"
os.environ["LLM_BACKOFF_BASE"] = "0"
os.environ["LLM_TIMEOUT"] = "2"

from fastapi.testclient import TestClient

from webui.server import app


def _pick_dice_indices(prompt: dict, state: dict) -> list[int]:
    """根据提示选择一个合法的确认列表（含必选骰子）。"""
    dices = state["you"]["dices"]
    selected = [i for i, d in enumerate(dices) if d["must_select"]]
    need = prompt["need"]
    target = max(len(selected), 1) if need == "any" else need
    for i in range(len(dices)):
        if len(selected) >= target:
            break
        if i not in selected:
            selected.append(i)
    return selected


def test_full_game_over_websocket():
    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "银河战力党" in resp.text

        with client.websocket_connect("/ws") as ws:
            menu = ws.receive_json()
            assert menu["type"] == "menu"
            assert menu["characters"], "可选角色列表为空"
            assert menu["special_dices"], "曜彩骰列表为空"

            ws.send_json(
                {
                    "type": "start",
                    "character": menu["characters"][0]["index"],
                    "special_dice": menu["special_dices"][0]["index"],
                    "seed": 42,
                }
            )

            prompts = 0
            settlements = 0
            for _ in range(2000):
                msg = ws.receive_json()
                assert msg["type"] in ("update", "error"), msg
                if msg["type"] == "error":
                    continue
                if msg["state"]:
                    you = msg["state"]["you"]
                    assert 0 <= you["hp"] <= you["max_hp"]
                settle = msg.get("settlement")
                if settle:
                    settlements += 1
                    for side in ("attacker", "defender"):
                        info = settle[side]
                        assert info["side"] in ("you", "opponent")
                        assert (
                            info["total"]
                            == (info["dice_sum"] + info["extra"]) * info["mult"]
                        )
                        assert info["dice_sum"] == sum(info["dices"])
                    assert settle["defender_hp_after"] <= settle["defender_hp_before"]
                if msg["game_over"] is not None:
                    assert (
                        msg["game_over"]["winner"] in ("you", "opponent", "draw")
                        or (msg["game_over"]["error"])
                    )
                    assert prompts > 0, "整局未出现任何人类决策点"
                    assert settlements > 0, "整局未捕获任何结算数据"
                    return
                if msg["prompt"]:
                    prompts += 1
                    ws.send_json(
                        {
                            "type": "action",
                            "action": 1,
                            "selected": _pick_dice_indices(msg["prompt"], msg["state"]),
                        }
                    )
            pytest.fail("对局未在预期消息数内结束")

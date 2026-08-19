"""FastAPI + WebSocket 服务器：托管静态前端并驱动对局会话。

启动方式：python -m webui [--host 127.0.0.1] [--port 8000]
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .session import GameSession, menu_payload

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="银河战力党 WebUI")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.websocket("/ws")
async def game_ws(ws: WebSocket) -> None:
    await ws.accept()
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[dict | None] = asyncio.Queue()
    session: GameSession | None = None

    async def sender() -> None:
        try:
            while True:
                msg = await queue.get()
                if msg is None:
                    return
                await ws.send_text(json.dumps(msg, ensure_ascii=False))
        except Exception:  # noqa: BLE001 - 连接断开时静默退出发送循环
            return

    def push(msg: dict) -> None:
        """游戏线程的推送回调，跨线程转发到事件循环。"""
        loop.call_soon_threadsafe(queue.put_nowait, msg)

    sender_task = asyncio.create_task(sender())
    try:
        await ws.send_text(json.dumps(menu_payload(), ensure_ascii=False))
        while True:
            data = json.loads(await ws.receive_text())
            msg_type = data.get("type")
            if msg_type == "start":
                if session is not None:
                    session.stop()
                try:
                    seed = data.get("seed")
                    # 构造中包含 LLM 选角（同步阻塞），放到工作线程执行
                    session = await asyncio.to_thread(
                        GameSession,
                        int(data["character"]),
                        int(data["special_dice"]),
                        int(seed) if seed is not None else None,
                        push,
                    )
                except (ValueError, KeyError, TypeError) as exc:
                    session = None
                    await ws.send_text(
                        json.dumps(
                            {"type": "error", "message": f"开局失败：{exc}"},
                            ensure_ascii=False,
                        )
                    )
                    continue
                session.start()
            elif msg_type == "action":
                ok = session is not None and session.submit_action(
                    int(data.get("action", 0)), data.get("selected", [])
                )
                if not ok:
                    await ws.send_text(
                        json.dumps(
                            {"type": "error", "message": "当前没有等待中的决策"},
                            ensure_ascii=False,
                        )
                    )
            elif msg_type == "stop":
                if session is not None:
                    session.stop()
    except WebSocketDisconnect:
        pass
    finally:
        if session is not None:
            session.stop()
        queue.put_nowait(None)
        await asyncio.gather(sender_task, return_exceptions=True)

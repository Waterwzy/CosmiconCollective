"""WebUI 启动入口：python -m webui [--host 127.0.0.1] [--port 8000]"""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="银河战力党 WebUI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    import uvicorn

    uvicorn.run("webui.server:app", host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()

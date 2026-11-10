"""Lifecycle owned by the Harness plugin; no browser launch or user setup."""
import asyncio
import json
import os
import socket
import sys
import threading
from pathlib import Path

import uvicorn

from .server import create_app
from .store import Store


def _serve():
    app = create_app(Store(Path(os.environ["PRC_DATA"])), os.environ["PRC_SESSION_TOKEN"])
    from .migrate_legacy import migrate
    migrate(app.state.store, app.state.coach)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    listener.setblocking(False)
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning", access_log=False))
    app.state.server, app.state.port = server, port

    def parent_watch():
        # stdin is a dedicated anonymous pipe. EOF means Harness exited.
        sys.stdin.buffer.read()
        server.should_exit = True

    threading.Thread(target=parent_watch, daemon=True).start()

    async def serve():
        task = asyncio.create_task(server.serve(sockets=[listener]))
        while not server.started and not task.done():
            await asyncio.sleep(0.03)
        if server.started:
            print(json.dumps({"event": "ready", "port": port}), flush=True)
        await task

    asyncio.run(serve())


def main():
    from filelock import FileLock
    directory = Path(os.environ["PRC_DATA"]) / "plugin-updates"
    directory.mkdir(parents=True, exist_ok=True)
    with FileLock(str(directory / "reader.lock"), timeout=0):
        _serve()


if __name__ == "__main__":
    main()

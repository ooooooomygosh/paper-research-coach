"""Open an authenticated local workbench, reusing its running service."""

from __future__ import annotations

import subprocess
import sys
import time
import webbrowser
from urllib.parse import urlencode

import httpx
from filelock import FileLock

from .server import session_token


def open_workbench(store, port=8765, paper_id="", conversation_id="", new=False):
    if not 1024 <= port <= 65535:
        raise ValueError("请选择有效的工作台端口。")
    paper_id = paper_id or store.setting("active-paper", "")
    if paper_id:
        store.get("paper", paper_id)
    if (conversation_id or new) and not paper_id:
        raise ValueError("请先选择论文，再打开这篇论文的对话。")
    base = f"http://127.0.0.1:{port}"
    token = session_token(store)
    with (
        FileLock(str(store.root / "workbench-open.lock"), timeout=15),
        httpx.Client(
            base_url=base,
            headers={"Authorization": "Bearer " + token},
            timeout=3,
            trust_env=False,
        ) as client,
    ):

        def running():
            try:
                response = client.get("/api/state")
            except httpx.ConnectError:
                return False
            except httpx.HTTPError:
                raise ValueError("工作台暂未响应，请稍后重新打开。") from None
            try:
                state = response.json()
            except ValueError:
                state = {}
            if (
                not response.is_success
                or not isinstance(state, dict)
                or not isinstance(state.get("papers"), list)
            ):
                raise ValueError(
                    "这个端口正在使用另一处服务，请检查工作台的数据目录与端口。"
                )
            return True

        if not running():
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "paper_research_coach.cli",
                    "--data-dir",
                    str(store.root),
                    "serve",
                    "--no-open",
                    "--port",
                    str(port),
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            deadline = time.monotonic() + 10
            while not running():
                if time.monotonic() >= deadline:
                    raise ValueError(
                        "工作台未能启动，请在 Codex 中让教练检查本机服务。"
                    )
                time.sleep(0.2)

        def post(path, body):
            try:
                response = client.post(path, json=body)
                result = response.json()
            except (httpx.HTTPError, ValueError):
                raise ValueError("工作台连接暂未完成，请重新打开。") from None
            if not response.is_success:
                raise ValueError(result.get("error", "阅读对话未能打开。"))
            return result

        if paper_id:
            if not conversation_id or new:
                conversation_id = post(
                    "/api/coach/connect/" + paper_id, {"new": bool(new)}
                )["id"]
            post(
                "/api/coach/active",
                {
                    "paper_id": paper_id,
                    "conversation_id": conversation_id,
                },
            )
    fragment = {"token": token}
    if paper_id:
        fragment.update(paper=paper_id, conversation=conversation_id)
    if not webbrowser.open(base + "/#" + urlencode(fragment)):
        raise ValueError(
            "浏览器未打开。请检查系统默认浏览器，或在 Codex 中打开工作台。"
        )
    return {"opened": True, "paper_id": paper_id, "conversation_id": conversation_id}

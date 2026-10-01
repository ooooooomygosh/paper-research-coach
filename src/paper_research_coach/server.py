from __future__ import annotations

import asyncio
import json
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from . import __version__
from .coach import Coach, Send
from .exports import export
from .models import Commit, uid
from .store import Conflict, Store
from .translation import (
    SelectionRequest,
    Translation,
    TranslationBatch,
    TranslationRequest,
    TranslationSettings,
)
from .vault import VaultSync
from .zotero import ZoteroSync


def session_token(store: Store):
    path = store.root / "session-token"
    if not path.exists():
        import os

        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(secrets.token_urlsafe(32))
        except FileExistsError:
            pass
    path.chmod(0o600)
    return path.read_text().strip()


def create_app(store: Store, token: str | None = None, sync: ZoteroSync | None = None):
    token = token or session_token(store)
    sync = sync or ZoteroSync(store)
    vault = VaultSync(store, sync)
    coach = Coach(store)
    translation = Translation(store)

    @asynccontextmanager
    async def lifespan(app):
        await translation.resume()
        async def loop():
            while True:
                state = sync.state()
                if state["enabled"]:
                    await asyncio.to_thread(sync.run)
                await asyncio.sleep(state["poll_seconds"])

        async def folder_loop():
            while True:
                if vault.state()["enabled"]:
                    try:
                        await asyncio.to_thread(vault.run)
                    except Exception:
                        # A transient folder/API failure must not stop future scans.
                        store.set_setting(
                            "vault",
                            vault.state()
                            | {
                                "state": "attention",
                                "message": "目录检查暂未完成，内容已保留；下一轮将重试。",
                            },
                        )
                await asyncio.sleep(vault.state()["poll_seconds"])

        folder_task = asyncio.create_task(folder_loop())
        task = asyncio.create_task(loop())
        yield
        task.cancel()
        folder_task.cancel()
        await coach.close()
        await translation.close()
        try:
            await asyncio.gather(task, folder_task)
        except asyncio.CancelledError:
            pass

    app = FastAPI(
        title="Paper Research Coach",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.store, app.state.sync = store, sync
    app.state.coach = coach
    app.state.translation = translation
    app.state.vault = vault

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        host = request.headers.get("host", "")
        if urlparse("http://" + host).hostname not in ("127.0.0.1", "localhost", "::1"):
            return JSONResponse({"error": "Local host required"}, 403)
        origin = request.headers.get("origin")
        if origin and origin != f"http://{host}":
            return JSONResponse({"error": "Cross-origin requests are disabled"}, 403)
        bearer = request.headers.get("authorization", "").removeprefix("Bearer ")
        cookie = request.cookies.get("prc_session", "")
        authorized = secrets.compare_digest(bearer, token) or secrets.compare_digest(
            cookie, token
        )
        if request.url.path.startswith("/api/") and request.url.path != "/api/login":
            if not authorized:
                return JSONResponse(
                    {"error": "这个浏览器尚未连接工作台，请从本机启动器打开。"}, 401
                )
            if (
                request.method not in ("GET", "HEAD")
                and not origin
                and not secrets.compare_digest(bearer, token)
            ):
                return JSONResponse(
                    {"error": "Origin required for browser writes"}, 403
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; font-src 'self' data:; img-src 'self' data: blob:; worker-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'"
        )
        return response

    @app.exception_handler(Conflict)
    async def conflict_handler(request, exc):
        return JSONResponse({"error": str(exc)}, 409)

    @app.exception_handler(KeyError)
    async def missing_handler(request, exc):
        return JSONResponse({"error": str(exc)}, 404)

    @app.exception_handler(ValueError)
    async def value_handler(request, exc):
        return JSONResponse({"error": str(exc)}, 400)

    @app.exception_handler(OSError)
    async def file_handler(request, exc):
        return JSONResponse({"error": "文件无法读取或写入，请检查路径和权限。"}, 400)

    @app.post("/api/login")
    async def login(request: Request):
        data = await request.json()
        if not secrets.compare_digest(str(data.get("token", "")), token):
            return JSONResponse({"error": "启动链接已失效，请从本机启动器重新打开。"}, 401)
        response = JSONResponse({"ok": True})
        response.set_cookie(
            "prc_session", token, httponly=True, samesite="strict", path="/"
        )
        return response

    @app.get("/api/state")
    def state():
        return {
            "papers": store.list("paper"),
            "sync": sync.state(),
            "conflicts": sync.conflicts(),
            "version": __version__,
            "vault": vault.state(),
            "vault_conflicts": vault.conflicts(),
        }

    @app.post("/api/commit")
    def commit(body: Commit):
        return store.commit(body)

    @app.get("/api/records/{kind}")
    def records(kind: str, paper_id: str | None = None):
        return store.list(kind, paper_id)

    @app.get("/api/context/{paper_id}")
    def context(paper_id: str, since: int = 0):
        return store.context(paper_id, since)

    @app.get("/api/history/{record_id}")
    def history(record_id: str):
        return store.history(record_id)

    @app.post("/api/import")
    async def import_path(request: Request):
        data = await request.json()
        return await asyncio.to_thread(
            store.add_paper,
            title=data["title"],
            source_path=data.get("path", ""),
            goal=data.get("goal", ""),
        )

    @app.post("/api/upload")
    async def upload(
        request: Request, title: str = "未命名论文", replace: str | None = None
    ):
        # Stream to a private managed copy. Never use a client-supplied filename.
        folder = store.root / "imports"
        folder.mkdir(exist_ok=True)
        path = folder / f"{uid()}.pdf"
        size = 0
        try:
            with path.open("xb") as f:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > 200 * 1024 * 1024:
                        raise ValueError("PDF 超过 200 MB，请使用本地路径导入。")
                    f.write(chunk)
            p = (
                await asyncio.to_thread(store.replace_source, replace, str(path))
                if replace
                else await asyncio.to_thread(store.add_paper, title, str(path))
            )
            if p["source_path"] != str(path):
                path.unlink(missing_ok=True)
            return p
        except Exception:
            path.unlink(missing_ok=True)
            raise

    @app.post("/api/source/{paper_id}")
    async def replace(paper_id: str, request: Request):
        return await asyncio.to_thread(
            store.replace_source, paper_id, (await request.json())["path"]
        )

    @app.get("/api/pdf/{paper_id}")
    def pdf(paper_id: str):
        if store.check_source(paper_id)["status"] != "current":
            raise Conflict("PDF 已换版或不可用，请先确认来源。")
        p = store.get("paper", paper_id)
        return FileResponse(
            p["source_path"],
            media_type="application/pdf",
            filename="paper.pdf",
            content_disposition_type="inline",
        )

    @app.get("/api/text/{paper_id}/{page_index}")
    def page_text(paper_id: str, page_index: int):
        from pypdf import PdfReader

        p = store.get("paper", paper_id)
        if (
            store.check_source(paper_id)["status"] != "current"
            or not 0 <= page_index < p["page_count"]
        ):
            raise ValueError("当前版本没有此页。")
        reader = PdfReader(p["source_path"])
        text = reader.pages[page_index].extract_text() or ""
        return {
            "text": text,
            "page_index": page_index,
            "page_label": reader.page_labels[page_index],
            "source_version": p["source_version"],
            "status": "text" if text.strip() else "needs_visual_reading",
            "untrusted_source": True,
        }

    @app.post("/api/review/{record_id}")
    async def answer(record_id: str, request: Request):
        data = await request.json()
        return store.review_answer(
            record_id,
            data["answer"],
            data["assistance"],
            data["success"],
            data["expected_revision"],
        )

    @app.get("/api/coach/status")
    async def coach_status():
        return await coach.status()

    @app.post("/api/coach/reconnect")
    async def coach_reconnect():
        if coach.active:
            raise Conflict("先停止正在进行的回复，再重新连接。")
        await coach.rpc.close()
        coach.resumed.clear()
        return await coach.status()

    @app.post("/api/coach/login")
    async def coach_login():
        await coach.rpc.start()
        if coach.login:
            return coach.login
        coach.login = await coach.rpc.call("account/login/start", {"type": "chatgpt"})
        return coach.login

    @app.get("/api/translation/settings")
    async def translation_settings():
        return {**translation.settings(), "component": await asyncio.to_thread(translation.component)}

    @app.post("/api/translation/settings")
    async def update_translation_settings(body: TranslationSettings):
        return translation.settings(body.model_dump())

    @app.get("/api/translation/jobs")
    async def all_translation_jobs():
        return await asyncio.to_thread(translation.overview)

    @app.post("/api/translation/batch")
    async def batch_translation(body: TranslationBatch):
        return await translation.batch(body)

    @app.get("/api/translation/{paper_id}/jobs")
    async def translation_jobs(paper_id: str):
        return {"data": [translation.public(j) for j in translation.jobs(paper_id)]}

    @app.post("/api/translation/{paper_id}/jobs")
    async def create_translation(paper_id: str, body: TranslationRequest):
        return await translation.create(paper_id, body)

    @app.get("/api/translation/jobs/{job_id}")
    async def translation_job(job_id: str):
        return translation.public(translation.job(job_id))

    @app.post("/api/translation/jobs/{job_id}/stop")
    async def stop_translation(job_id: str):
        return await translation.stop(job_id)

    @app.post("/api/translation/jobs/{job_id}/retry")
    async def retry_translation(job_id: str):
        return await translation.retry(job_id)

    @app.get("/api/translation/jobs/{job_id}/pdf/{kind}")
    async def translation_pdf(job_id: str, kind: str):
        return FileResponse(translation.artifact(job_id, kind), media_type="application/pdf")

    @app.post("/api/translation/jobs/{job_id}/selection")
    async def translation_selection(job_id: str, body: SelectionRequest):
        return await asyncio.to_thread(translation.selection, job_id, body)

    @app.get("/api/coach/threads")
    async def coach_threads(paper_id: str):
        return {"data": coach.conversations(paper_id), "nextCursor": None}

    @app.post("/api/coach/active")
    async def coach_active(request: Request):
        data = await request.json()
        paper_id = data["paper_id"]
        store.get("paper", paper_id)
        if data.get("conversation_id"):
            conversation = coach.conversation(data["conversation_id"])
            if conversation["paper_id"] != paper_id:
                raise ValueError("对话不属于当前论文")
            canonical = coach.binding(paper_id)["conversation_id"]
            if conversation["id"] != canonical:
                raise ValueError("历史对话为只读，请返回当前论文对话。")
            store.set_setting("coach-current:" + paper_id, canonical)
        store.set_setting("active-paper", paper_id)
        return {"paper_id": paper_id}

    @app.post("/api/coach/connect/{paper_id}")
    async def coach_connect(paper_id: str, request: Request):
        data = await request.json()
        return await coach.connect(paper_id, str(data.get("thread_id", "")), bool(data.get("new", False)))

    @app.get("/api/coach/conversation/{paper_id}")
    def coach_conversation(paper_id: str, conversation_id: str = ""):
        return coach.snapshot(paper_id, conversation_id)

    @app.post("/api/coach/send/{paper_id}")
    async def coach_send(paper_id: str, body: Send):
        return await coach.send(paper_id, body)

    @app.post("/api/coach/stop/{conversation_id}")
    async def coach_stop(conversation_id: str):
        coach.conversation(conversation_id)
        return await coach.stop(conversation_id)

    @app.post("/api/coach/save-message/{conversation_id}/{message_id}")
    async def save_chat_message(conversation_id: str, message_id: str):
        conversation = coach.conversation(conversation_id)
        message = next((m for m in coach.messages(conversation_id) if m["id"] == message_id), None)
        if not message or not message["content"].strip():
            raise ValueError("没有可保存的对话内容")
        note_id = "chat-" + message_id
        try:
            return store.get("note", note_id)
        except KeyError:
            pass
        anchor = message.get("anchor")
        if anchor and anchor["source_version"] != store.get("paper", conversation["paper_id"])["source_version"]:
            anchor = {**anchor, "status": "stale"}
        result = store.commit({"operation_id": "coach-note:" + message_id, "mutations": [{"kind": "note", "data": {
            "id": note_id, "paper_id": conversation["paper_id"], "content": message["content"], "anchor": anchor,
            "author": message["role"], "provenance": "USER" if message["role"] == "user" else "INFERENCE",
        }}]})
        return result["records"][0]

    @app.get("/api/coach/events/{paper_id}")
    async def coach_events(paper_id: str, request: Request, conversation_id: str = ""):
        coach.snapshot(paper_id, conversation_id)

        async def stream():
            previous = ""
            while not await request.is_disconnected():
                data = json.dumps(coach.snapshot(paper_id, conversation_id), ensure_ascii=False)
                if data != previous:
                    yield "data: " + data + "\n\n"
                    previous = data
                else:
                    yield ": keepalive\n\n"
                await asyncio.sleep(.35)

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"})

    @app.post("/api/export")
    async def export_file(request: Request):
        data = await request.json()
        result = await asyncio.to_thread(
            export, store, data["kind"], data.get("paper_id"), rendition=data.get("rendition")
        )
        return {
            "download": "/api/download/" + Path(result["path"]).name,
            "unplaced_note_ids": result.get("unplaced_note_ids", []),
        }

    @app.get("/api/download/{filename}")
    def download(filename: str):
        path = (store.root / "exports" / filename).resolve()
        if path.parent != (store.root / "exports").resolve() or not path.is_file():
            raise KeyError("Export not found")
        return FileResponse(path, filename=path.name)

    @app.get("/api/events")
    async def events(request: Request, since: int = 0):
        try:
            since = max(since, int(request.headers.get("last-event-id", "0")))
        except ValueError:
            pass

        async def stream():
            cursor = since
            while not await request.is_disconnected():
                rows = await asyncio.to_thread(store.events, cursor)
                if rows:
                    cursor = rows[-1]["seq"]
                    yield f"id: {cursor}\ndata: {json.dumps(rows)}\n\n"
                else:
                    yield ": keepalive\n\n"
                await asyncio.sleep(1)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no"},
        )

    @app.get("/api/zotero/collections")
    def collections():
        try:
            return sync.collections()
        except Exception:
            raise ValueError("无法连接 Zotero，请启动应用并允许本地应用通信。")

    @app.post("/api/zotero/configure")
    async def configure(request: Request):
        data = await request.json()
        return await asyncio.to_thread(
            sync.configure,
            data["server_id"],
            data["collection"],
            data.get("enabled", True),
        )

    @app.post("/api/zotero/authorize")
    async def authorize(request: Request):
        data = await request.json()
        try:
            return await asyncio.to_thread(sync.authorize, data["server_id"])
        except Exception:
            raise ValueError("授权尚未完成，请在 Zotero 中确认，或重新发起授权。")

    @app.post("/api/zotero/sync")
    async def synchronize():
        return await asyncio.to_thread(sync.run)

    @app.post("/api/sync/refresh")
    async def refresh_sync():
        result = {}
        if vault.state().get("root"):
            result["vault"] = await asyncio.to_thread(vault.run, manual=True)
        if sync.state().get("collection"):
            result["zotero"] = await asyncio.to_thread(sync.run)
        return result

    @app.post("/api/zotero/conflict/{conflict_id}")
    async def resolve(conflict_id: str, request: Request):
        return await asyncio.to_thread(
            sync.resolve, conflict_id, (await request.json())["choice"]
        )

    @app.post("/api/vault/configure")
    async def vault_configure(request: Request):
        data = await request.json()
        return await asyncio.to_thread(
            vault.configure,
            data["root"],
            sync.state()["collection"],
            sync.state()["server_id"],
        )

    @app.post("/api/vault/scan")
    async def vault_scan():
        return await asyncio.to_thread(vault.run, manual=True)

    @app.post("/api/vault/conflict/{conflict_id}")
    async def vault_resolve(conflict_id: str, request: Request):
        return await asyncio.to_thread(
            vault.resolve, conflict_id, (await request.json())["choice"]
        )

    static = Path(__file__).parent / "static"

    @app.get("/{path:path}")
    def frontend(path: str):
        file = (static / path).resolve()
        if file.is_relative_to(static.resolve()) and file.is_file():
            return FileResponse(file)
        index = static / "index.html"
        if index.is_file():
            return FileResponse(index)
        return JSONResponse(
            {
                "error": "Frontend is missing. Build frontend or install the release wheel."
            },
            503,
        )

    return app

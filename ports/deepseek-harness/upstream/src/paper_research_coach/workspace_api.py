from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import Request
from fastapi.responses import FileResponse, Response

from .workspaces import WorkspaceStore, Jobs, Account, artifact_document, valid_id
from .studio import Studio

ARTIFACT_CSP = "sandbox allow-scripts allow-forms allow-downloads allow-modals; default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; media-src data: blob:; connect-src 'none'; frame-ancestors 'self'; form-action 'none'; base-uri 'none'; object-src 'none'"


class Workspace:
    def __init__(self, papers, text_factory=None, renderer=None):
        self.papers = papers
        self.store = WorkspaceStore(papers.root / "workspaces")
        self.jobs = Jobs(self.store)
        self.account = Account(self.store, text_factory, renderer)
        self.studio = Studio(self.store, self.jobs, self.account, self.context, self.interactive_sources)
        self.learning = None

    def state(self):
        summary_fields = {"id", "title", "revision", "state", "published", "created_at", "updated_at", "question", "theme", "depth", "materials", "needs_rebuild", "language"}
        return {"studios": [{key: value for key, value in row.items() if key in summary_fields} for row in self.store.list("studio") if not row.get("archived")],
                "kbs": [{key: value for key, value in row.items() if key in summary_fields} for row in self.store.list("kb") if not row.get("archived")],
                "jobs": self.store.list("job")[:100], "provider": "deepseek-account", "brand": "Paper Research Coach"}

    async def context(self, source, question=""):
        if source.get("kb_id"):
            if not self.learning:
                raise ValueError("知识库学习服务未就绪。")
            return self.learning.context(source["kb_id"], question, source.get("unit_id"), source.get("version"), source.get("method_id"))
        if source.get("paper_id"):
            paper_id = valid_id(source["paper_id"])
            paper = self.papers.get("paper", paper_id)
            if source.get("source_version") and source["source_version"] != paper["source_version"]:
                raise ValueError("所选论文已换版，请重新选择来源。")
            if self.papers.check_source(paper_id)["status"] != "current":
                raise ValueError("论文 PDF 已变化或不可用，请重新核对来源。")
            page = int(source.get("page_index", 0))

            def read():
                import pypdfium2 as pdfium
                with pdfium.PdfDocument(paper["source_path"]) as document:
                    if page < 0 or page >= len(document):
                        raise ValueError("来源页码无效。")
                    item = document[page]
                    try:
                        text = item.get_textpage()
                        try:
                            return text.get_text_range()
                        finally:
                            text.close()
                    finally:
                        item.close()

            text = await asyncio.to_thread(read)
            if len(text) > 24000:
                text = text[:24000] + "\n[本页过长，当前仅提供开头部分。]"
            return f"论文：{paper['title']}，PDF 第 {page + 1} 页\n{text}\n用户选区：{str(source.get('quote', ''))[:4000]}"
        return str(source.get("text", ""))[:24000]

    async def interactive_sources(self, source, question=""):
        if source.get("paper_id"):
            paper = self.papers.get("paper", valid_id(source["paper_id"]))
            page = int(source.get("page_index", 0))
            label = f"论文：{paper['title']}，PDF 第 {page + 1} 页"
            # Use only PDF text, not the separately supplied selection or metadata.
            context = await self.context({**source, "quote": ""}, question)
            text = context.removeprefix(label + "\n").removesuffix("\n用户选区：").removesuffix("\n[本页过长，当前仅提供开头部分。]")
            return [{"id": "pdf-page", "label": label, "text": text, "context": {**source, "source_version": paper["source_version"]}, "anchor": {
                "paper_id": paper["id"], "source_version": paper["source_version"], "page_index": page, "status": "verified", "rects": []}}]
        if source.get("kb_id"):
            _, _, publication = self.learning.publication(source["kb_id"], source.get("version"))
            context = {**source, "version": publication["version"]}
            blocks = self.learning.retrieve(source["kb_id"], question, source.get("unit_id"), publication["version"], source.get("method_id"))
            return [{"id": block["id"], "label": block["source"], "text": block["text"][:24000], "context": context} for block in blocks]
        return []

    def storage(self, kind, item_id, payload):
        if kind not in ("studio", "kb"):
            raise ValueError("未知的学习页面类型。")
        key, value = str(payload.get("key", "")), payload.get("value")
        if not key or len(key) > 500 or (value is not None and (not isinstance(value, str) or len(value) > 500000)):
            raise ValueError("学习记录超过大小限制。")
        row = self.store.get(kind, item_id)
        storage = dict(row.get("storage", {}))
        if value is None:
            storage.pop(key, None)
        else:
            storage[key] = value
        if len(storage) > 500 or len(json.dumps(storage, ensure_ascii=False)) > 2_000_000:
            raise ValueError("此页面的本地学习记录过大，请先导出。")
        self.store.patch(kind, item_id, {"storage": storage})
        return {"saved": True}

    def artifact(self, kind, item_id, filename, version=None):
        if kind not in ("studio", "kb") or filename not in ("page.html", "page.md", "page.json", "knowledge.zip", "methods.json", "methodology.json"):
            raise ValueError("未知的导出类型。")
        row = self.store.get(kind, item_id)
        versions = ([row["published"]] if row.get("published") else []) + row.get("history", [])
        publication = next((p for p in versions if p["version"] == version), None) if version else row.get("published")
        if not publication:
            raise ValueError("还没有可打开的学习页面，请先生成。")
        path = self.store.directory(kind, item_id) / valid_id(publication["version"]) / filename
        if not path.is_file():
            raise ValueError("请求的文件尚未生成。")
        return row, path

    async def close(self):
        await self.jobs.close()


def mount_workspace(app, workspace):
    from .learning import mount_learning
    from .paper_study import mount_paper_study
    mount_learning(app, workspace)
    mount_paper_study(app, workspace)
    @app.get("/api/workspace")
    def state():
        return workspace.state()

    @app.post("/api/workspace/studios")
    async def create(request: Request):
        return workspace.studio.create(await request.json())

    @app.get("/api/workspace/studios/{item_id}")
    def studio(item_id: str):
        return workspace.store.get("studio", item_id)

    @app.put("/api/workspace/studios/{item_id}")
    async def update(item_id: str, request: Request):
        return workspace.studio.update(item_id, await request.json())

    @app.post("/api/workspace/studios/{item_id}/render")
    async def render(item_id: str):
        if workspace.jobs.active(item_id):
            raise ValueError("正在生成，请稍候或停止后再渲染。")
        return await workspace.studio.render(item_id)

    @app.post("/api/workspace/studios/{item_id}/generate")
    async def generate(item_id: str, request: Request):
        return workspace.studio.generate(item_id, await request.json())

    @app.get("/api/workspace/jobs/{job_id}")
    def job(job_id: str):
        return workspace.store.get("job", job_id)

    @app.post("/api/workspace/jobs/{job_id}/cancel")
    async def cancel(job_id: str):
        return await workspace.jobs.cancel(job_id)

    @app.put("/api/workspace/storage/{kind}/{item_id}")
    async def storage(kind: str, item_id: str, request: Request):
        return workspace.storage(kind, item_id, await request.json())

    @app.get("/api/workspace/view/{kind}/{item_id}")
    def view(kind: str, item_id: str, version: str | None = None):
        row, path = workspace.artifact(kind, item_id, "page.html", version)
        document = artifact_document(path.read_text(encoding="utf-8"), item_id=item_id, kind=kind, storage=row.get("storage", {}))
        return Response(document, media_type="text/html")

    @app.get("/api/workspace/export/{kind}/{item_id}/{filename}")
    def export(kind: str, item_id: str, filename: str, version: str | None = None):
        row, path = workspace.artifact(kind, item_id, filename, version)
        title = "".join(c for c in row["title"][:80] if c not in '<>:"/\\|?*\r\n') or "Paper Research Coach"
        return FileResponse(path, filename=title + path.suffix)

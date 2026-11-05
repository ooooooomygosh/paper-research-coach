"""Persistent workspace records and cancellable account-owned jobs."""
from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from uuid import uuid4

import httpx


PACKAGE = Path(__file__).resolve().parents[3]
INTEGRATIONS = PACKAGE / "integrations"


def now():
    return datetime.now(timezone.utc).isoformat()


def identifier(prefix=""):
    return prefix + uuid4().hex[:16]


def valid_id(value):
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", str(value)):
        raise ValueError("工作区编号无效。")
    return str(value)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


class WorkspaceStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.database = self.root / "workspace.sqlite3"
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS items(kind TEXT, id TEXT, data TEXT, PRIMARY KEY(kind,id))")
        # A restart never silently reruns an account request.
        for job in self.list("job"):
            if job["state"] in ("queued", "running"):
                self.patch("job", job["id"], {"state": "interrupted", "message": "应用已重启；已完成内容保留，可继续。"})

    def connection(self):
        return sqlite3.connect(self.database, timeout=20)

    def create(self, kind, value):
        value = {"id": identifier(kind + "-"), "revision": 1, "created_at": now(), "updated_at": now(), **value}
        valid_id(value["id"])
        with self.connection() as db:
            db.execute("INSERT INTO items VALUES(?,?,?)", (kind, value["id"], json.dumps(value, ensure_ascii=False)))
        return value

    def get(self, kind, item_id):
        valid_id(item_id)
        with self.connection() as db:
            row = db.execute("SELECT data FROM items WHERE kind=? AND id=?", (kind, item_id)).fetchone()
        if not row:
            raise ValueError("工作区记录不存在。")
        return json.loads(row[0])

    def list(self, kind):
        with self.connection() as db:
            rows = db.execute("SELECT data FROM items WHERE kind=? ORDER BY rowid DESC", (kind,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def patch(self, kind, item_id, patch, expected=None):
        valid_id(item_id)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT data FROM items WHERE kind=? AND id=?", (kind, item_id)).fetchone()
            if not row:
                raise ValueError("工作区记录不存在。")
            current = json.loads(row[0])
            if expected is not None and expected != current["revision"]:
                raise ValueError("内容已在其他窗口更新，请刷新后重试。")
            value = current | patch | {"id": item_id, "revision": current["revision"] + 1, "updated_at": now()}
            db.execute("UPDATE items SET data=? WHERE kind=? AND id=?", (json.dumps(value, ensure_ascii=False), kind, item_id))
        return value

    def directory(self, kind, item_id):
        self.get(kind, item_id)
        directory = self.root / kind / valid_id(item_id)
        directory.mkdir(parents=True, exist_ok=True)
        return directory


class Jobs:
    def __init__(self, store):
        self.store = store
        self.tasks = {}

    def active(self, owner):
        return next((j for j in self.store.list("job") if j["owner"] == owner and j["state"] in ("queued", "running")), None)

    def start(self, owner, kind, operation, *, metadata=None):
        if self.active(owner):
            raise ValueError("此工作区已有任务进行中，请先停止或等待完成。")
        job = self.store.create("job", {"owner": owner, "kind": kind, "state": "queued", "stage": "等待开始", "done": 0, "total": 0, "message": "", **(metadata or {})})

        async def run():
            self.progress(job["id"], state="running", stage="开始处理")
            try:
                result = await operation(job["id"])
                self.progress(job["id"], state="completed", stage="已完成", result=result, message="")
            except asyncio.CancelledError:
                self.progress(job["id"], state="cancelled", stage="已停止", message="已完成内容保留，可以继续。")
            except Exception as error:
                message = str(error) if isinstance(error, ValueError) else "本次任务未完成，请检查资料、账户连接后重试。"
                self.progress(job["id"], state="failed", stage="需要处理", message=message[:2000])
            finally:
                self.tasks.pop(job["id"], None)

        self.tasks[job["id"]] = asyncio.create_task(run())
        return job

    def progress(self, job_id, **patch):
        return self.store.patch("job", job_id, patch)

    async def cancel(self, job_id):
        job = self.store.get("job", job_id)
        task = self.tasks.get(job_id)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        elif job["state"] in ("queued", "running", "interrupted"):
            self.progress(job_id, state="cancelled", stage="已停止")
        return self.store.get("job", job_id)

    async def close(self):
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


class Account:
    def __init__(self, store, text_factory=None, renderer=None):
        self.store = store
        if text_factory is None and os.environ.get("PRC_EMBEDDED") == "1":
            from .dsh_bridge import deepseek_text
            text_factory = deepseek_text
        self.text_factory = text_factory
        self.renderer = renderer

    async def text(self, prompt, instructions, schema=None, *, model="", effort="high"):
        if self.text_factory is None:
            raise ValueError("请在 DeepSeek Harness 中打开 Paper Research Coach 并登录账户。")
        client = self.text_factory(self.store.root / "model", model, effort)
        try:
            return await client.text(prompt, schema=schema, instructions=instructions)
        except ValueError as error:
            raise ValueError(str(error).replace("翻译", "内容生成")) from None
        finally:
            await client.close()

    async def render(self, source, theme="paper", template="doc", language="zh"):
        if self.renderer:
            return await self.renderer({"source": source, "theme": theme, "template": template, "language": language})
        endpoint = os.environ.get("DSH_PRC_BRIDGE_URL")
        token = os.environ.get("DSH_PRC_BRIDGE_TOKEN")
        if not endpoint or not token:
            raise ValueError("交互页面渲染服务未就绪，请在 Harness 中重新打开插件。")
        async with httpx.AsyncClient(trust_env=False, timeout=90) as client:
            response = await client.post(endpoint + "/render-html", headers={"Authorization": "Bearer " + token},
                                         json={"source": source, "theme": theme, "template": template, "language": language})
            if response.status_code != 200:
                raise ValueError(response.json().get("error", "讲解草稿需要修改。"))
            return response.json()


def artifact_document(raw, *, item_id, kind, storage):
    """Keep upstream script pins; relay only this opaque frame's local reader state."""
    bootstrap = """(()=>{
const scope=__SCOPE__, initial=__STORAGE__, values={...initial};
const send=(kind,extra={})=>parent.postMessage({channel:'prc-workspace-v1',scope,kind,...extra},'*');
const storage={getItem:k=>Object.hasOwn(values,k)?values[k]:null,setItem:(k,v)=>{k=String(k);v=String(v);values[k]=v;send('storage',{key:k,value:v})},removeItem:k=>{delete values[k];send('storage',{key:k,value:null})},clear:()=>{Object.keys(values).forEach(k=>storage.removeItem(k))},key:i=>Object.keys(values)[i]??null};
Object.defineProperty(storage,'length',{get:()=>Object.keys(values).length});
try{Object.defineProperty(window,'localStorage',{get:()=>storage})}catch{}
addEventListener('DOMContentLoaded',()=>{
 const button=document.createElement('button');button.type='button';button.textContent='带回 Paper Research Coach';button.title='将选中文字、页面回答或当前问题带入教练输入框，由你确认发送';
 button.style.cssText='position:fixed;right:12px;bottom:12px;z-index:9999;padding:9px 13px;border:1px solid #b6c8b9;border-radius:12px;background:#f5faf5;color:#264c35;font:12px system-ui;cursor:pointer;box-shadow:0 3px 16px #0002';
 button.addEventListener('click',()=>{const selection=getSelection()?.toString().trim();const inputs=[...document.querySelectorAll('textarea,input:checked')].filter(e=>e.getClientRects().length&&!e.closest('[hidden],[aria-hidden="true"]')).map(e=>e.value?.trim()).filter(Boolean);send('question',{text:(selection||inputs.join('\\n')||document.title).slice(0,16000)})});document.body.append(button);
 document.addEventListener('click',e=>{const deep=e.target.closest('[data-deep-dive]');if(deep){e.preventDefault();e.stopImmediatePropagation();send('question',{text:'请结合资料解释：'+(deep.dataset.concept||deep.textContent)+'\\n出处：'+(deep.dataset.sourceRef||'')})}},true);
 const line=String.fromCharCode(10);
 document.addEventListener('click',e=>{const control=e.target.closest('[data-ch-send]');if(!control)return;const page=JSON.parse(document.getElementById('pageData')?.textContent||'{}'),unit=(page.contentUnits||[]).find(u=>u.id===control.dataset.chSend);if(unit){e.preventDefault();e.stopImmediatePropagation();send('question',{unit_id:unit.id,text:('请结合原文详细解释这个学习单元：'+unit.title+line+unit.core+line+(unit.takeaways||[]).join(line)+line+'出处：'+unit.source).slice(0,16000)})}},true);
 document.addEventListener('click',e=>{if(e.target.closest('#assessmentCopy')){const text=document.getElementById('assessmentPromptPreview')?.value;if(text)send('question',{text:text.slice(0,16000)})}});
 document.addEventListener('submit',e=>{if(e.target.id==='methodForm'){const text=document.getElementById('methodPrompt')?.value,selected=document.getElementById('methodSelect')?.value;if(text)send('question',{text:text.slice(0,16000),method_id:['whole','auto'].includes(selected)?null:selected})}});
});
})();""".replace("__SCOPE__", json.dumps({"id": item_id, "type": kind})).replace("__STORAGE__", json.dumps(storage, ensure_ascii=False).replace("<", "\\u003c"))
    pin = "'sha256-" + base64.b64encode(hashlib.sha256(bootstrap.encode()).digest()).decode() + "'"
    if re.search(r'<meta\s+http-equiv="Content-Security-Policy"', raw, re.I):
        raw = re.sub(r'(<meta\s+http-equiv="Content-Security-Policy"\s+content="[^"]*?script-src )', lambda m: m[1] + pin + " ", raw, count=1, flags=re.I)
    else:
        scripts = re.findall(r'<script(\s[^>]*)?>([\s\S]*?)</script\s*>', raw, re.I)
        pins = [pin] + ["'sha256-" + base64.b64encode(hashlib.sha256(body.encode()).digest()).decode() + "'" for attrs, body in scripts if 'application/json' not in attrs]
        policy = "default-src 'none'; script-src " + " ".join(pins) + "; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; media-src data: blob:; connect-src 'none'; form-action 'none'; base-uri 'none'"
        raw = raw.replace("<head>", '<head><meta http-equiv="Content-Security-Policy" content="' + policy + '">', 1)
    return raw.replace("</head>", "<script>" + bootstrap + "</script></head>", 1)

"""Harness account adapter for the existing coach and translation protocols.

The workbench owns tool execution and reading constraints. Harness owns model
selection, authentication, request preparation and transport. No provider secret
is read, copied or persisted here.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
from pathlib import Path
from uuid import uuid4

import httpx


def identifier():
    return uuid4().hex


class DeepSeekRPC:
    def __init__(self, handler, cwd: Path):
        self.handler, self.cwd = handler, Path(cwd)
        self.cwd.mkdir(parents=True, exist_ok=True)
        self.root = self.cwd / "deepseek-threads"
        self.root.mkdir(exist_ok=True)
        self.client = None
        self.threads = {}
        self.tasks = {}
        self.pending = {}
        self.closing = False

    async def start(self):
        if self.client is None or self.client.is_closed:
            self.closing = False
            self.client = httpx.AsyncClient(
                base_url=os.environ["DSH_PRC_BRIDGE_URL"],
                headers={"Authorization": "Bearer " + os.environ["DSH_PRC_BRIDGE_TOKEN"]},
                timeout=httpx.Timeout(600, connect=10),
                trust_env=False,
            )

    async def state(self):
        await self.start()
        try:
            response = await self.client.get("/state")
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError):
            raise ValueError("DeepSeek Harness 账户连接未就绪，请检查登录后重试。") from None

    def thread_path(self, thread_id):
        if not re.fullmatch(r"[a-f0-9]{32}", thread_id):
            raise ValueError("阅读会话编号无效。")
        return self.root / (thread_id + ".json")

    def load(self, thread_id):
        if thread_id not in self.threads:
            try:
                self.threads[thread_id] = json.loads(self.thread_path(thread_id).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raise ValueError("阅读会话记录不可用，请新建对话。") from None
        return self.threads[thread_id]

    def save(self, thread):
        if thread.get("ephemeral"):
            return
        target = self.thread_path(thread["id"])
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(thread, ensure_ascii=False), encoding="utf-8")
        temporary.replace(target)

    async def call(self, method, params, timeout=45):
        await self.start()
        if method in ("config/read", "account/read", "model/list"):
            state = await self.state()
            if method == "config/read":
                return {"config": {"model_provider": "deepseek-account", "model": state["model"], "model_reasoning_effort": ""}}
            if method == "account/read":
                return {"requiresOpenaiAuth": True, "account": {"type": "deepseek-account"} if state["signedIn"] else None}
            return {"data": state["models"]}
        if method == "thread/start":
            tid = identifier()
            thread = {"id": tid, "cwd": params.get("cwd", str(self.cwd)), "ephemeral": params.get("ephemeral", False), "system": params.get("developerInstructions", ""), "tools": params.get("dynamicTools", []), "model": params.get("model", ""), "messages": []}
            self.threads[tid] = thread
            self.save(thread)
            return {"thread": {"id": tid}}
        if method == "thread/resume":
            thread = self.load(params["threadId"])
            for source, key in (("developerInstructions", "system"), ("dynamicTools", "tools"), ("model", "model")):
                if source in params:
                    thread[key] = params[source]
            self.save(thread)
            return {"thread": {"id": thread["id"]}}
        if method == "thread/list":
            data = []
            for file in self.root.glob("*.json"):
                with contextlib.suppress(OSError, ValueError):
                    item = json.loads(file.read_text(encoding="utf-8"))
                    if item["cwd"] == params.get("cwd"):
                        data.append({"id": item["id"]})
            return {"data": data, "nextCursor": None}
        if method == "turn/start":
            thread = self.load(params["threadId"])
            if thread["id"] in self.tasks and not self.tasks[thread["id"]].done():
                raise ValueError("这篇论文已有回复正在进行。")
            turn_id = identifier()
            self.tasks[thread["id"]] = asyncio.create_task(self.run(thread, params, turn_id))
            return {"turn": {"id": turn_id}}
        if method == "turn/interrupt":
            task = self.tasks.get(params["threadId"])
            if task:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            return {}
        if method == "thread/unsubscribe":
            thread = self.threads.get(params["threadId"], {})
            if thread.get("ephemeral"):
                self.threads.pop(params["threadId"], None)
            return {}
        if method.startswith("account/login"):
            raise ValueError("请直接在 DeepSeek Harness 设置中登录账户，然后返回继续阅读。")
        raise ValueError("不支持的阅读运行时操作。")

    async def write(self, value):
        future = self.pending.get(value.get("id"))
        if future and not future.done():
            future.set_result(value.get("result") or {"success": False, "contentItems": [{"type": "inputText", "text": "操作未完成。"}]})

    async def notify(self, method, thread_id, turn_id, **params):
        await self.handler({"method": method, "params": {"threadId": thread_id, "turnId": turn_id, **params}})

    async def run(self, thread, params, turn_id):
        tid = thread["id"]
        content = []
        for part in params.get("input", []):
            if part["type"] == "text":
                content.append({"type": "text", "text": part["text"]})
            elif part["type"] == "image":
                content.append({"type": "inline-image", "url": part["url"]})
        thread["messages"].append({"id": identifier(), "role": "user", "source": {"kind": "user"}, "content": content})
        self.save(thread)
        system = thread["system"]
        if params.get("outputSchema"):
            system += "\n只输出有效 JSON，不加 Markdown 围栏。必须满足以下 JSON Schema：\n" + json.dumps(params["outputSchema"], ensure_ascii=False)
        status, error = "completed", None
        try:
            for _ in range(64):
                blocks, text_items, partials = {}, {}, {}
                finish, route = None, {"provider": "deepseek-account", "model": params.get("model") or thread["model"]}
                payload = {"model": params.get("model") or thread["model"], "effort": params.get("effort", ""), "system": system, "messages": thread["messages"], "tools": [{"name": t["name"], "description": t["description"], "parameters": t["inputSchema"]} for t in thread["tools"]]}
                async with self.client.stream("POST", "/stream", json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        chunk = json.loads(line)
                        kind, index = chunk.get("type"), chunk.get("index", 0)
                        if kind == "route":
                            route = {"provider": chunk["provider"], "model": chunk["model"]}
                        elif kind == "text-delta":
                            if index not in text_items:
                                text_items[index] = identifier()
                                await self.notify("item/started", tid, turn_id, item={"id": text_items[index], "type": "agentMessage", "phase": "final_answer"})
                            partials[index] = partials.get(index, "") + chunk["text"]
                            await self.notify("item/agentMessage/delta", tid, turn_id, itemId=text_items[index], delta=chunk["text"])
                        elif kind == "block-end":
                            blocks[index] = chunk["block"]
                        elif kind == "finish":
                            finish = chunk
                if not finish:
                    raise ValueError("DeepSeek 响应提前中断。")
                if finish["reason"]["kind"] in ("error", "aborted", "max-tokens"):
                    code = finish["reason"].get("failure", {}).get("code", "MODEL_ERROR")
                    mapped = {"ACCOUNT_SIGN_IN_REQUIRED": "unauthorized", "ACCOUNT_TOKEN_INVALID": "unauthorized", "RATE_LIMIT": "rateLimitExceeded", "ACCOUNT_QUOTA_EXCEEDED": "usageLimitExceeded"}
                    error = {"codexErrorInfo": mapped.get(code, "serverOverloaded")}
                    status = "failed"
                for index, item_id in text_items.items():
                    await self.notify("item/completed", tid, turn_id, item={"id": item_id, "type": "agentMessage", "phase": "final_answer", "text": blocks.get(index, {}).get("text", partials.get(index, ""))})
                for index, text in partials.items():
                    blocks.setdefault(index, {"type": "text", "text": text})
                ordered = [blocks[i] for i in sorted(blocks)]
                source = {"kind": "model", **route}
                if finish.get("replayState") is not None:
                    source["replayState"] = finish["replayState"]
                if ordered:
                    thread["messages"].append({"id": identifier(), "role": "assistant", "source": source, "content": ordered})
                    self.save(thread)
                calls = [block for block in ordered if block["type"] == "tool-call"]
                if status != "completed":
                    # Never persist an unpaired call from a truncated response.
                    if calls:
                        thread["messages"][-1]["content"] = [b for b in ordered if b["type"] != "tool-call"]
                        thread["messages"][-1]["source"].pop("replayState", None)
                        self.save(thread)
                    break
                if not calls:
                    break
                for call in calls:
                    call_id = call["id"]
                    future = asyncio.get_running_loop().create_future()
                    self.pending[call_id] = future
                    try:
                        try:
                            arguments = json.loads(call["arguments"])
                        except ValueError:
                            result = {"success": False, "contentItems": [{"type": "inputText", "text": "工具参数不是有效 JSON，请修正后重试。"}]}
                        else:
                            await self.handler({"id": call_id, "method": "item/tool/call", "params": {"threadId": tid, "turnId": turn_id, "tool": call["name"], "arguments": arguments, "callId": call_id}})
                            result = await asyncio.wait_for(future, 120)
                        output = []
                        for item in result.get("contentItems", []):
                            if item["type"] == "inputText":
                                output.append({"type": "text", "text": item["text"]})
                            elif item["type"] == "inputImage":
                                output.append({"type": "inline-image", "url": item["imageUrl"]})
                        thread["messages"].append({"id": identifier(), "role": "tool", "source": {"kind": "tool", "callId": call_id}, "toolCallId": call_id, "isError": not result.get("success", False), "content": output})
                        self.save(thread)
                    finally:
                        self.pending.pop(call_id, None)
            else:
                status, error = "failed", {"codexErrorInfo": "toolLimitExceeded"}
        except asyncio.CancelledError:
            status = "interrupted"
        except Exception:
            status, error = "failed", {"codexErrorInfo": "connectionFailed"}
        finally:
            # Interrupted tool batches receive deterministic cancellation results
            # so the next user turn always has replayable provider history.
            answered = {m["toolCallId"] for m in thread["messages"] if m["role"] == "tool"}
            for message in list(thread["messages"]):
                if message["role"] == "assistant":
                    for block in message["content"]:
                        if block["type"] == "tool-call" and block["id"] not in answered:
                            position = thread["messages"].index(message) + 1
                            thread["messages"].insert(position, {"id": identifier(), "role": "tool", "source": {"kind": "tool", "callId": block["id"]}, "toolCallId": block["id"], "isError": True, "content": [{"type": "text", "text": "此操作已中断。"}]})
            self.save(thread)
            await self.notify("turn/completed", tid, turn_id, turn={"id": turn_id, "status": status, "error": error})

    async def close(self):
        self.closing = True
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.tasks.clear()
        if self.client is not None:
            await self.client.aclose()


def deepseek_text(cwd, model, effort="low"):
    from .codex_text import CodexText
    return CodexText(cwd, model, effort, rpc_factory=DeepSeekRPC)

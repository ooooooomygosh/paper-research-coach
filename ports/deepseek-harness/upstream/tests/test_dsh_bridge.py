import asyncio
import json

import httpx

from paper_research_coach.dsh_bridge import DeepSeekRPC


def test_tool_loop_stream_persistence_and_resume(tmp_path, monkeypatch):
    monkeypatch.setenv("DSH_PRC_BRIDGE_URL", "http://127.0.0.1:9999")
    monkeypatch.setenv("DSH_PRC_BRIDGE_TOKEN", "private-test")

    async def run():
        events, requests = [], []
        async def handler(event):
            events.append(event)
            if event.get("method") == "item/tool/call":
                content = [{"type": "inputText", "text": "verbatim source evidence"}]
                if event["params"]["tool"] == "prc_view_page":
                    content.append({"type": "inputImage", "imageUrl": "data:image/png;base64,aW1hZ2U="})
                await rpc.write({"id": event["id"], "result": {"success": True, "contentItems": content}})
        rpc = DeepSeekRPC(handler, tmp_path)
        async def transport(request):
            if request.url.path == "/state":
                return httpx.Response(200, json={"model": "flash", "signedIn": True, "models": [{"model": "flash"}]})
            body = json.loads(request.content)
            requests.append(body)
            if len(requests) == 1:
                chunks = [{"type": "block-end", "index": 0, "block": {"type": "tool-call", "id": "read-call", "name": "prc_read_page", "arguments": '{"page_index": 0}'}}, {"type": "block-end", "index": 1, "block": {"type": "tool-call", "id": "view-call", "name": "prc_view_page", "arguments": '{"page_index": 0}'}}, {"type": "finish", "reason": {"kind": "tool-calls"}}]
            else:
                assert body["messages"][-1]["toolCallId"] == "view-call"
                assert [m["role"] for m in body["messages"][-3:]] == ["assistant", "tool", "tool"]
                assert body["messages"][-1]["content"][1]["type"] == "inline-image"
                chunks = [{"type": "text-delta", "index": 0, "text": "Evidence checked."}, {"type": "block-end", "index": 0, "block": {"type": "text", "text": "Evidence checked."}}, {"type": "finish", "reason": {"kind": "stop"}, "replayState": {"response": {"id": "model-native-id"}}}]
            return httpx.Response(200, content="\n".join(json.dumps(c) for c in chunks))
        rpc.client = httpx.AsyncClient(base_url="http://127.0.0.1:9999", transport=httpx.MockTransport(transport))
        thread = (await rpc.call("thread/start", {"model": "flash", "developerInstructions": "coach", "dynamicTools": [{"name": "prc_read_page", "description": "read", "inputSchema": {"type": "object"}}]}))["thread"]["id"]
        await rpc.call("turn/start", {"threadId": thread, "input": [{"type": "text", "text": "Read evidence"}]})
        await rpc.tasks[thread]
        assert len(requests) == 2
        assert any(e.get("method") == "item/agentMessage/delta" for e in events)
        assert events[-1]["params"]["turn"]["status"] == "completed"
        await rpc.close()
        second = DeepSeekRPC(handler, tmp_path)
        assert second.load(thread)["messages"][-1]["source"]["replayState"]["response"]["id"] == "model-native-id"
        assert second.load(thread)["messages"][-1]["content"][0]["text"] == "Evidence checked."
    asyncio.run(run())


def test_interruption_finishes_and_retains_user_input(tmp_path, monkeypatch):
    monkeypatch.setenv("DSH_PRC_BRIDGE_URL", "http://127.0.0.1:9999")
    monkeypatch.setenv("DSH_PRC_BRIDGE_TOKEN", "private-test")
    async def run():
        started = asyncio.Event()
        events = []
        async def handler(event): events.append(event)
        rpc = DeepSeekRPC(handler, tmp_path)
        async def transport(request):
            started.set()
            await asyncio.sleep(600)
        rpc.client = httpx.AsyncClient(base_url="http://127.0.0.1:9999", transport=httpx.MockTransport(transport))
        tid = (await rpc.call("thread/start", {}))["thread"]["id"]
        await rpc.call("turn/start", {"threadId": tid, "input": [{"type": "text", "text": "Keep this question"}]})
        await started.wait()
        await rpc.call("turn/interrupt", {"threadId": tid})
        assert events[-1]["params"]["turn"]["status"] == "interrupted"
        assert rpc.load(tid)["messages"][0]["content"][0]["text"] == "Keep this question"
        await rpc.close()
    asyncio.run(run())

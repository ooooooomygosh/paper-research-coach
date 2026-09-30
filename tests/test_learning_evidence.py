import asyncio
import json

import pytest

from paper_research_coach.coach import Coach, Send
from paper_research_coach.store import Conflict
from test_coach import FakeRPC, drained


def test_legacy_selection_grounds_text_in_selected_page_and_preserves_retry(store, paper, anchor):
    async def run():
        coach = Coach(store, FakeRPC)
        body = Send(operation_id="old-durable-send", content="解释我选择的证据", anchor=anchor, page_index=1)
        fingerprint = body.fingerprint_data()
        result = await coach.send(paper["id"], body)
        await drained(coach)
        assert coach.messages(result["conversation_id"])[0]["page_index"] == 0
        params = next(p for method, p in coach.rpc.calls if method == "turn/start")
        assert "PDF 第 1 页" in params["input"][0]["text"]
        assert "Budget-matched evidence" in params["input"][1]["text"]
        assert params["input"][-1]["text"] == body.content
        assert "Repeated quote" not in str(params)
        assert body.fingerprint_data() == fingerprint
        assert await coach.send(paper["id"], body) == result
        assert len([m for m, _ in coach.rpc.calls if m == "turn/start"]) == 1
        await coach.close()
    asyncio.run(run())


def test_learning_evidence_requires_consent_exact_answer_and_read_source(store, paper):
    async def run():
        coach = Coach(store, FakeRPC)
        coach.rpc.hold = True
        result = await coach.send(paper["id"], Send(operation_id="answer", content="我认为还需要预算相同的对照，否则不能排除额外信息的收益。", intent="answer", help_mode="hint"))
        state = coach.active[result["conversation_id"]]
        for _ in range(100):
            if state.get("turn_id"):
                break
            await asyncio.sleep(0.01)
        assert not state["read_pages"]
        coach.tool_call(state, "prc_read_page", {"page_index": 0}, "explicit-evidence")
        args = dict(ability="evidence", answer_quote="还需要预算相同的对照", assistance="prompt-only", judgment="supported", criterion="区分机制收益与额外信息收益，需要预算匹配的对照。", feedback="你提出了可区分替代解释的对照；还需要检查实际图表是否支持。", page_index=0)
        with pytest.raises(ValueError, match="未开启"):
            coach.tool_call(state, "prc_record_learning_evidence", args, "consent")
        session = store.list("session", paper["id"])[0]
        store.commit({"mutations": [{"kind": "session", "data": {**session, "learning_consent": True}, "expected_revision": session["revision"]}]})
        for key, value, match in [("answer_quote", "这其实是 AI 编造的回答", "逐字"), ("page_index", 1, "先读取"), ("assistance", "independent", "独立")]:
            with pytest.raises(ValueError, match=match):
                coach.tool_call(state, "prc_record_learning_evidence", {**args, key: value}, "invalid-" + key)
        saved = coach.tool_call(state, "prc_record_learning_evidence", args, "save")
        assert coach.tool_call(state, "prc_record_learning_evidence", args, "save") == saved
        session = store.list("session", paper["id"])[0]
        observation = session["support_evidence"]["evidence"]
        assert observation["message_id"] == result["message_id"]
        assert observation["anchor"]["source_version"] == paper["source_version"]
        assert observation["assistance"] == "prompt-only"
        assert not session["support"]  # One local observation is not a mastery promotion.
        assert not store.list("note", paper["id"])  # Feedback opt-in is separate from note consent.
        state["intent"] = "follow"
        with pytest.raises(ValueError, match="继续按钮"):
            coach.tool_call(state, "prc_record_learning_evidence", args, "follow")
        state["intent"] = "answer"
        state["source_version"] = "old"
        with pytest.raises(Conflict, match="换版"):
            coach.tool_call(state, "prc_record_learning_evidence", args, "version")
        await coach.close()
    asyncio.run(run())

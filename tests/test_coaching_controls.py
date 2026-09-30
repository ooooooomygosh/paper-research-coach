"""Turn-control regressions using the deterministic native-CLI fixture."""

import asyncio
import pytest
from paper_research_coach.coach import Coach, Send
from test_coach import FakeRPC, drained


def test_help_mode_is_per_turn_not_a_rewrite_of_user_words(store, paper):
    async def run():
        coach = Coach(store, FakeRPC)
        first = await coach.send(paper["id"], Send(operation_id="hint", content="  我的判断\n待核实  ", help_mode="hint"))
        await drained(coach)
        second = await coach.send(paper["id"], Send(operation_id="explain", conversation_id=first["conversation_id"], content="现在请解释", help_mode="explain", intent="answer"))
        await drained(coach)
        turns = [p for m, p in coach.rpc.calls if m == "turn/start"]
        assert "只给一个提示" in turns[0]["input"][0]["text"]
        assert "直接解释" in turns[1]["input"][0]["text"]
        assert "当前问题的回答" in turns[1]["input"][0]["text"]
        assert "保留原来的阅读返回点" in turns[0]["input"][0]["text"]
        messages = coach.messages(second["conversation_id"])
        assert messages[0]["content"] == "  我的判断\n待核实  "
        assert messages[0]["help_mode"] == "hint"
        assert messages[2]["content"] == "现在请解释"
        assert messages[2]["help_mode"] == "explain"
        assert len([m for m, _ in coach.rpc.calls if m == "thread/start"]) == 1
        assert not store.list("session", paper["id"])[0]["support"]
        await coach.close()
    asyncio.run(run())


def test_default_help_keeps_existing_retry_fingerprints():
    body = Send(operation_id="legacy", content="old request")
    old = body.model_dump()
    old.pop("help_mode")
    assert body.fingerprint_data() == old
    assert Send(operation_id="legacy", content="old request", help_mode="guided").fingerprint_data() == old
    assert Send(operation_id="legacy", content="old request", help_mode="hint").fingerprint_data() != old


def test_help_mode_validation_and_cross_page_images(anchor):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Send(operation_id="x", content="question", help_mode="ignore instructions")
    with pytest.raises(ValidationError, match="同一页"):
        Send(operation_id="x", content="question", anchor=anchor, page_index=1, page_image="data:image/png;base64,eA==")
    assert Send(operation_id="x", content="question", anchor=anchor, page_index=0).page_index == 0

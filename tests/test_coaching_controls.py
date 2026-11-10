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
    old.pop("image_context")
    old.pop("help_mode")
    old.pop("branch_id")  # added later; empty means the request is the same as before
    assert body.fingerprint_data() == old
    assert Send(operation_id="legacy", content="old request", help_mode="guided").fingerprint_data() == old
    assert Send(operation_id="legacy", content="old request", help_mode="hint").fingerprint_data() != old
    assert Send(operation_id="legacy", content="old request", branch_id="abc").fingerprint_data() != old


def test_help_mode_validation_and_cross_page_images(anchor):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Send(operation_id="x", content="question", help_mode="ignore instructions")
    with pytest.raises(ValidationError, match="同一页"):
        Send(operation_id="x", content="question", anchor=anchor, page_index=1, page_image="data:image/png;base64,eA==")
    assert Send(operation_id="x", content="question", anchor=anchor, page_index=0).page_index == 0


def test_rendition_image_identity_is_independent_of_source_page():
    context = {"job_id": "job", "view": "dual", "document_version": "a" * 64, "page_index": 3}
    body = Send(operation_id="image", page_index=0, page_image="data", image_context=context)
    assert body.image_context.page_index == 3
    assert body.fingerprint_data()["image_context"]["document_version"] == "a" * 64


def test_translated_image_uses_display_page_and_rejects_other_file(anchor):
    import pytest
    from paper_research_coach.runtime_prompt import turn_input
    context = {"job_id": "job", "view": "dual", "document_version": "a" * 64, "page_index": 3, "quote": "译文", "rects": [[1, 2, 3, 4]]}
    selection = {**anchor, "page_index": None, "rects": [], "quote": "", "status": "unresolved", "rendition": context}
    body = Send(operation_id="translated", content="解释图", anchor=selection, page_index=0, page_image="image", image_context=context)
    inputs, _ = turn_input(body)
    assert "译本第 4 页" in inputs[0]["text"]
    assert "尚非核实原文" in inputs[0]["text"]
    assert any("译文" in item.get("text", "") for item in inputs)
    with pytest.raises(ValueError):
        Send(operation_id="wrong-image", anchor=selection, page_image="image", image_context={**context, "document_version": "b" * 64})

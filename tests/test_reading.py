import asyncio
import base64
import io
from pathlib import Path

import pytest
from PIL import Image
from test_coach import FakeRPC, drained

from paper_research_coach import reading
from paper_research_coach.coach import Coach, Send
from paper_research_coach.models import uid
from paper_research_coach.pdf_visual import view_page
from paper_research_coach.store import Conflict


def turn(coach, paper, intent="follow"):
    conversation = asyncio.run(coach.connect(paper["id"]))
    answer = {"id": uid(), "conversation_id": conversation["id"], "role": "assistant", "content": "", "status": "streaming", "actions": []}
    coach.save_message(answer)
    return {"conversation": conversation, "answer": answer, "intent": intent, "source_version": paper["source_version"], "read_pages": set(), "flow_advanced": False, "stop": False}


def start(store, paper):
    session = store.list("session", paper["id"])[0]
    with store.connect() as db:
        return reading.begin(store, paper, session, db)


def test_follow_needs_no_prompt_and_does_not_capture_a_fake_learner_thought(store, paper):
    session = store.list("session", paper["id"])[0]
    store.put("session", {**session, "note_consent": True}, session["revision"])

    async def run():
        coach = Coach(store, FakeRPC)
        request = Send(operation_id="start-route", intent="follow")
        sent = await coach.send(paper["id"], request)
        await drained(coach)
        assert await coach.send(paper["id"], request) == sent
        assert not store.list("note", paper["id"])
        flow = coach.snapshot(paper["id"])["reading_flow"]
        assert flow["status"] == "active" and flow["current"] == "orient"
        assert len(flow["steps"]) == 8
        message = coach.messages(sent["conversation_id"])[0]
        assert message["intent"] == "follow"
        await coach.connect(paper["id"], new=True)
        assert coach.snapshot(paper["id"])["reading_flow"] == flow
        await coach.close()
    asyncio.run(run())


def test_detour_cannot_advance_or_overwrite_the_return_point(store, paper):
    start(store, paper)
    coach = Coach(store, FakeRPC)
    state = turn(coach, paper, "detour")
    session = store.list("session", paper["id"])[0]
    result = coach.tool_call(state, "prc_next_action", {"stage": "transfer", "next_action": "Forget the route", "pending_question": "A different topic"}, "side-question")
    assert result["preserved"]
    assert store.get("session", session["id"]) == session
    with pytest.raises(ValueError, match="插话"):
        coach.tool_call(state, "prc_complete_reading_step", {"step": "orient", "evidence": "A claim", "page_index": 0}, "advance")


def test_route_requires_order_viewed_evidence_and_a_real_recall_attempt(store, paper):
    old_review = store.put("review", {"paper_id": paper["id"], "prompt": "An earlier reading round"})
    store.review_answer(old_review["id"], "A previous answer", "none", True, old_review["revision"])
    start(store, paper)
    coach = Coach(store, FakeRPC)
    for index, step in enumerate(reading.KEYS):
        state = turn(coach, paper)
        args = {"step": step, "evidence": "Budget matching distinguishes the competing explanations.", "page_index": 0}
        with pytest.raises(ValueError, match="实际读取"):
            coach.tool_call(state, "prc_complete_reading_step", args, "unread")
        coach.tool_call(state, "prc_read_page", {"page_index": 0}, "read")
        if index == 0:
            with pytest.raises(ValueError, match="跳过"):
                coach.tool_call(state, "prc_complete_reading_step", {**args, "step": "method"}, "skip")
        if step == "recall":
            with pytest.raises(ValueError, match="真实回忆"):
                coach.tool_call(state, "prc_complete_reading_step", args, "no-answer")
            review = store.put("review", {"paper_id": paper["id"], "prompt": "How would you distinguish the explanations?"})
            review = store.review_answer(review["id"], " ", "hint", True, review["revision"])
            with pytest.raises(ValueError, match="真实回忆"):
                coach.tool_call(state, "prc_complete_reading_step", args, "empty-answer")
            store.review_answer(review["id"], "Use equal information budgets.", "hint", True, review["revision"])
            context = coach.tool_call(state, "prc_context", {}, "feedback-context")
            assert not context["due_reviews"]
            assert context["reviews"][-1]["attempts"][-1]["answer"] == "Use equal information budgets."
        coach.tool_call(state, "prc_complete_reading_step", args, "complete-" + step)
        with pytest.raises(ValueError, match="最多完成一个"):
            coach.tool_call(state, "prc_complete_reading_step", args, "again")
    flow = coach.snapshot(paper["id"])["reading_flow"]
    assert flow["status"] == "completed"
    assert [s["step"] for s in flow["completed"]] == list(reading.KEYS)
    assert store.get("paper", paper["id"])["status"] == "done"
    assert flow["return_action"]


def test_route_is_per_paper_and_rechecks_a_changed_pdf(store, paper, tmp_path):
    start(store, paper)
    other = store.add_paper("Other paper")
    coach = Coach(store, FakeRPC)
    assert coach.snapshot(other["id"])["reading_flow"]["status"] == "not_started"
    state = turn(coach, paper)
    coach.tool_call(state, "prc_read_page", {"page_index": 0}, "page")
    changed = tmp_path / "changed.pdf"
    from reportlab.pdfgen import canvas
    pdf = canvas.Canvas(str(changed)); pdf.drawString(30, 50, "Changed evidence"); pdf.save()
    store.replace_source(paper["id"], str(changed))
    with pytest.raises(Conflict):
        coach.tool_call(state, "prc_complete_reading_step", {"step": "orient", "evidence": "Old evidence", "page_index": 0}, "old")
    assert coach.snapshot(paper["id"])["reading_flow"]["needs_recheck"]


def test_page_visual_is_real_bounded_and_rejects_stale_or_outside_pages(store, paper):
    before = Path(paper["source_path"]).read_bytes()
    rendered = view_page(store, paper["id"], 0)
    picture = Image.open(io.BytesIO(base64.b64decode(rendered["image_url"].split(",", 1)[1])))
    assert max(picture.size) <= 1800 and min(picture.size) > 600
    assert len(picture.convert("L").getcolors()) > 2
    assert rendered["source_version"] == paper["source_version"]
    assert Path(paper["source_path"]).read_bytes() == before
    with pytest.raises(ValueError):
        view_page(store, paper["id"], 99)
    with open(paper["source_path"], "ab") as pdf:
        pdf.write(b"\nchanged")
    with pytest.raises(Conflict):
        view_page(store, paper["id"], 0)


def test_comment_keeps_region_note_discussed_without_changing_its_location(store, paper, anchor):
    note = store.put("note", {"paper_id": paper["id"], "content": "My region thought", "anchor": anchor})
    note = store.get("note", note["id"])
    coach = Coach(store, FakeRPC)
    state = turn(coach, paper, "detour")
    coach.tool_call(state, "prc_comment_note", {"note_id": note["id"], "content": "A linked comment"}, "region-comment")
    saved = store.get("note", note["id"])
    assert saved["discussed"]
    assert saved["anchor"] == note["anchor"]
    assert saved["content"] == note["content"]
    assert not store.context(paper["id"])["pending_thoughts"]

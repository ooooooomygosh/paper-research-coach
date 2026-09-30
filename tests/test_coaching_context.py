import asyncio
import copy
import json

import pytest

from paper_research_coach.coach import Coach
from paper_research_coach.coaching_context import model_context, dialogue_excerpt
from test_coach import FakeRPC


def test_large_context_is_bounded_with_exact_excerpts_and_no_database_rewrite(store, paper):
    context = store.context(paper["id"])
    context["notes"] = [{"id": f"n-{index}", "paper_id": paper["id"], "author": "user", "provenance": "USER", "discussed": False, "updated_at": str(index).zfill(3), "content": "我的原话不是 AI 总结。\n" * 4000, "anchor": {"page_index": index % 2, "quote": "原文" * 5000, "source_version": paper["source_version"], "rects": [[1, 2, 3, 4]] * 200}} for index in range(80)]
    context["pending_thoughts"] = context["notes"]
    original = copy.deepcopy(context)
    bounded = model_context(context, page_index=1, current_note_id="n-79")
    assert len(json.dumps(bounded, ensure_ascii=False)) <= 36000
    assert bounded["notes"][0]["id"] == "n-79"
    assert bounded["context_scope"]["notes_omitted"] > 0
    assert bounded["notes"][0]["truncated"]
    assert bounded["notes"][0]["content"] == original["notes"][79]["content"][:1600]
    assert "source_path" not in bounded["paper"]
    assert context == original


def test_migrated_dialogue_has_a_budget_and_retains_recent_original_words():
    messages = [{"id": str(i), "role": "user", "content": f"原话 {i} " * 5000} for i in range(40)]
    selected = dialogue_excerpt(messages)
    assert len(json.dumps(selected, ensure_ascii=False)) <= 22000
    assert selected[-1]["id"] == "39"
    assert selected[-1]["content"] == messages[-1]["content"][:3000]
    assert selected[-1]["truncated"]
    assert len(messages[0]["content"]) > 3000
    short = [{"id": str(i), "role": "user", "content": "原话"} for i in range(500)]
    assert len(json.dumps(dialogue_excerpt(short), ensure_ascii=False)) <= 22000


def test_omitted_notes_can_be_read_in_exact_scoped_chunks(store, paper):
    async def run():
        coach = Coach(store, FakeRPC)
        conversation = await coach.connect(paper["id"])
        state = {"conversation": conversation, "stop": False, "answer": {"id": "context-check", "actions": []}, "message": {"page_index": 0, "id": "request"}}
        for i in range(30):
            store.put("note", {"id": f"note-{i}", "paper_id": paper["id"], "content": f"完整原话 {i}\n" * 1000})
        context = coach.tool_call(state, "prc_context", {}, "context")
        included = {n["id"] for n in context["notes"]}
        omitted = next(n for n in store.list("note", paper["id"]) if n["id"] not in included)
        chunk = coach.tool_call(state, "prc_read_note", {"note_id": omitted["id"], "start": 200, "length": 500}, "read")
        assert chunk["content"] == omitted["content"][200:700]
        assert chunk["truncated"] and chunk["untrusted_source"]
        listing = coach.tool_call(state, "prc_list_notes", {"offset": 20, "limit": 5}, "list")
        assert listing["total"] == 30 and listing["next_offset"] == 25
        other = store.add_paper("Other")
        foreign = store.put("note", {"paper_id": other["id"], "content": "另一篇论文的私有思考"})
        with pytest.raises(ValueError, match="当前论文"):
            coach.tool_call(state, "prc_read_note", {"note_id": foreign["id"]}, "foreign-note")
        other_conversation = await coach.connect(other["id"])
        with pytest.raises(ValueError, match="当前论文"):
            coach.tool_call(state, "prc_read_dialogue", {"conversation_id": other_conversation["id"]}, "foreign-chat")
        with pytest.raises(ValueError, match="范围"):
            coach.tool_call(state, "prc_read_note", {"note_id": omitted["id"], "length": 200000}, "oversized")
        assert store.get("note", omitted["id"])["content"] == omitted["content"]
        await coach.close()
    asyncio.run(run())

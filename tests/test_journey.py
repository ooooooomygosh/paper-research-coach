from test_coach import FakeRPC
from test_explainer import DRAFT
from test_reading import start, turn

from paper_research_coach import exports, journey
from paper_research_coach.coach import Coach
from paper_research_coach.models import uid


def say(coach, conversation_id, role, content, **extra):
    message = {"id": uid(), "conversation_id": conversation_id, "role": role, "content": content, "status": "completed",
               "actions": [], **extra}
    coach.save_message(message)
    return message


def test_journey_files_answers_side_quests_and_notes_under_their_chapters(store, paper, pdf):
    # A note written before the route starts belongs to no chapter.
    store.put("note", {"paper_id": paper["id"], "content": "first impression"})
    start(store, paper)
    coach = Coach(store, FakeRPC)
    state = turn(coach, paper, "follow")
    cid = state["conversation"]["id"]
    say(coach, cid, "assistant", "> 预设带读示例\n\n先看摘要。你觉得这篇要解决什么？还有别的。", step="orient", intent="follow",
        task={"question": "这篇要解决什么？", "choices": []},
        actions=[{"kind": "focus", "id": "f1", "anchor": {"page_index": 0}, "marks": [{"n": 1, "quote": "We show"}]}])
    mine = "  它想比较两种观测策略，  看预算是否公平 "
    say(coach, cid, "user", mine, step="orient", intent="answer")
    say(coach, cid, "assistant", "对，这正是要判断的。接下来看引言。", step="orient", intent="answer")
    say(coach, cid, "user", "old question without a chapter", intent="detour")
    say(coach, cid, "assistant", "Old reply.", intent="detour")
    coach.tool_call(state, "prc_read_page", {"page_index": 0}, "r1")
    coach.tool_call(state, "prc_complete_reading_step", {"step": "orient", "evidence": "p1", "page_index": 0,
                                                         "takeaway": "我要判断提升是不是来自预算。"}, "c1")
    # A side quest opened during chapter 2, closed by the reader in their own words.
    page = coach.explain_external(paper["id"], DRAFT, question="为什么不公平？")
    coach.explain_external(paper["id"], DRAFT, branch_id=page["id"])
    coach.set_quest(page["id"], "done", "预算不同就不能直接比。")
    store.put("note", {"paper_id": paper["id"], "content": "my thought in chapter 2"})

    trip = journey.build(store, paper["id"])
    orient, insight = trip["chapters"][:2]
    assert [c["status"] for c in trip["chapters"][:3]] == ["done", "current", "todo"]
    assert orient["takeaway"] == "我要判断提升是不是来自预算。"
    assert orient["exchanges"] == [{"text": mine.strip(), "message_id": orient["exchanges"][0]["message_id"],
                                    "reply": "对，这正是要判断的。", "reply_id": orient["exchanges"][0]["reply_id"],
                                    "page_index": None, "task": "这篇要解决什么？"}]
    assert orient["marks"] == [{"quote": "We show", "page_index": 0, "message_id": orient["marks"][0]["message_id"]}]
    [quest] = insight["side_quests"]
    assert quest["title"] == "Why the comparison is not fair" and quest["pages"] == 2
    assert quest["status"] == "done" and quest["takeaway"] == "预算不同就不能直接比。"
    assert quest["question"] == "为什么不公平？" and quest["gist"] == "the two policies use different budgets."
    assert [n["text"] for n in insight["notes"]] == ["my thought in chapter 2"]
    # Without a chapter, things go to "other"; nothing is invented.
    assert [n["text"] for n in trip["other"]["notes"]] == ["first impression"]
    assert [q["text"] for q in trip["other"]["questions"]] == ["old question without a chapter"]
    assert trip["other"]["questions"][0]["reply"] == "Old reply."
    assert not any(c["exchanges"] or c["side_quests"] or c["marks"] for c in trip["chapters"][2:])
    assert trip["counts"] == {"chapters_done": 1, "chapters": 8, "side_quests": 1, "side_quests_done": 1, "answers": 1}
    assert trip["verdict"] == ""
    # The paper card export carries the same tree.
    card = exports.paper_card(store, paper["id"])
    assert "## 主线与支线" in card and "我的回答：" + mine.strip() in card and "我的收获：预算不同就不能直接比。" in card


def test_journey_of_an_unread_paper_is_empty_and_needs_no_coach(store, paper):
    trip = journey.build(store, paper["id"])
    assert trip["status"] == "not_started" and trip["counts"]["answers"] == 0
    assert all(c["status"] == "todo" for c in trip["chapters"])
    assert "## 主线与支线" not in exports.paper_card(store, paper["id"])


def test_first_sentence_skips_the_preset_label_and_markup():
    assert journey.first_sentence("> **预设带读示例**\n\n**对**，[这里](x)说得清楚。后面还有。") == "对，这里说得清楚。"
    assert journey.first_sentence("Yes. The budget matters.") == "Yes."

import asyncio

from test_coach import FakeRPC, drained

from paper_research_coach import reading
from paper_research_coach.coach import Coach, Send


def test_every_step_has_a_method_guide():
    assert set(reading.GUIDES) == set(reading.KEYS)


def test_mainline_turns_carry_the_current_step_method(store, paper):
    async def run():
        coach = Coach(store, FakeRPC)
        await coach.send(paper["id"], Send(operation_id="start", content="", intent="follow"))
        await drained(coach)
        turn = [p for m, p in coach.rpc.calls if m == "turn/start"][-1]
        guide = turn["input"][1]["text"]
        assert "第 1/8 步「阅读目标」" in guide
        assert "非线性顺序" in guide
        await coach.close()

    asyncio.run(run())


def test_detour_keeps_the_mainline_and_answer_checks_the_learner(store, paper):
    flow = {"status": "active", "current": "evidence", "label": "证据核查", "goal": "g", "pending_question": "Q" * 999}
    detour = reading.turn_guide(flow, "detour")
    assert "第 5/8 步" in detour and "不推进" in detour
    answer = reading.turn_guide(flow, "answer")
    assert "预测" in answer and "原话" in answer and "Q" * 251 not in answer
    assert reading.turn_guide({"status": "not_started"}, "detour") == ""


def test_mainline_card_assigns_a_task_with_place_check_and_depth():
    flow = {"status": "active", "current": "method", "label": "方法机制", "goal": "g", "pending_question": "", "depth": "skim"}
    card = reading.turn_guide(flow, "follow")
    assert set(reading.CHECKS) == set(reading.LOOKS) == set(reading.KEYS)
    assert reading.CHECKS["method"] in card and reading.LOOKS["method"] in card
    assert "速读" in card and "prc_show" in card and "choices" in card and "takeaway" in card
    assert "同一条回复里布置下一步" in card
    assert "研读" in reading.turn_guide({**flow, "depth": "reconstruct"}, "answer")


def test_snapshot_exposes_the_task_and_drops_choices_without_a_question(store, paper):
    session = store.list("session", paper["id"])[0]
    flow = reading.snapshot({**session, "pending_question": "Which baseline?", "choices": ["A", "B"]}, paper)
    assert flow["choices"] == ["A", "B"] and flow["check"] == reading.CHECKS["orient"] and flow["look"]
    assert reading.snapshot({**session, "pending_question": "", "choices": ["A", "B"]}, paper)["choices"] == []

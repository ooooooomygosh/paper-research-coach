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

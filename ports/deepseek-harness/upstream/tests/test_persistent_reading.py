import asyncio

import pytest
from test_coach import FakeRPC, drained

from paper_research_coach.coach import Coach, ProtocolError, Send
from paper_research_coach.runtime_prompt import bootstrap


def test_concurrent_connect_and_restart_keep_one_binding(store, paper):
    async def run():
        coach = Coach(store, FakeRPC)
        rows = await asyncio.gather(
            *(coach.connect(paper["id"], new=True) for _ in range(20))
        )
        assert len({r["id"] for r in rows}) == 1
        first = await coach.send(
            paper["id"],
            Send(
                operation_id="first", content="A distinct judgment", model="first-model"
            ),
        )
        await drained(coach)
        native = coach.conversation(first["conversation_id"])["thread_id"]
        await coach.close()
        coach = Coach(store, FakeRPC)
        assert (
            coach.snapshot(paper["id"])["conversation_id"] == first["conversation_id"]
        )
        second = await coach.send(
            paper["id"],
            Send(
                operation_id="second",
                content="Resume this judgment",
                model="another-model",
            ),
        )
        await drained(coach)
        assert coach.conversation(second["conversation_id"])["thread_id"] == native
        assert not any(m == "thread/start" for m, p in coach.rpc.calls)
        assert any(
            m == "thread/resume" and p["threadId"] == native for m, p in coach.rpc.calls
        )
        assert "A distinct judgment" not in str(
            next(p for m, p in coach.rpc.calls if m == "turn/start")
        )
        with store.connect() as db:
            assert (
                db.execute(
                    "SELECT COUNT(*) FROM coach_paper_bindings WHERE paper_id=?",
                    (paper["id"],),
                ).fetchone()[0]
                == 1
            )
        await coach.close()

    asyncio.run(run())


def test_unknown_creation_is_reconciled_without_second_start(store, paper):
    class LostResponse(FakeRPC):
        async def call(self, method, params):
            if method == "thread/start":
                self.calls.append((method, params))
                raise ValueError("Connection lost after creation")
            if method == "thread/list":
                self.calls.append((method, params))
                return {"data": [{"id": "created-despite-timeout"}], "nextCursor": None}
            return await super().call(method, params)

    async def run():
        coach = Coach(store, LostResponse)
        conversation = await coach.connect(paper["id"])
        with pytest.raises(ValueError):
            await coach.native_thread(conversation, {"modelProvider": "openai"})
        assert coach.binding(paper["id"])["creation_state"] == "creating"
        assert (
            await coach.native_thread(conversation, {"modelProvider": "openai"})
            == "created-despite-timeout"
        )
        assert sum(m == "thread/start" for m, p in coach.rpc.calls) == 1
        assert coach.binding(paper["id"])["thread_id"] == "created-despite-timeout"
        await coach.close()

    asyncio.run(run())


def test_ambiguous_creation_and_failed_resume_preserve_binding(store, paper):
    class Reject(FakeRPC):
        async def call(self, method, params):
            if method == "thread/resume":
                raise ProtocolError({"message": "unavailable"})
            if method == "thread/list":
                return {"data": [], "nextCursor": None}
            return await super().call(method, params)

    async def run():
        coach = Coach(store, Reject)
        conversation = await coach.connect(paper["id"])
        with store.connect() as db:
            db.execute(
                "UPDATE coach_paper_bindings SET creation_state='creating' WHERE paper_id=?",
                (paper["id"],),
            )
        with pytest.raises(ValueError, match="尚未确认"):
            await coach.native_thread(conversation, {"modelProvider": "openai"})
        assert not any(m == "thread/start" for m, p in coach.rpc.calls)
        with store.connect() as db:
            db.execute(
                "UPDATE coach_paper_bindings SET thread_id='persisted-id',creation_state='ready' WHERE paper_id=?",
                (paper["id"],),
            )
        with pytest.raises(ProtocolError):
            await coach.native_thread(conversation, {"modelProvider": "openai"})
        assert coach.binding(paper["id"])["thread_id"] == "persisted-id"
        assert not any(m == "thread/start" for m, p in coach.rpc.calls)
        await coach.close()

    asyncio.run(run())


def test_initialization_and_turns_have_bounded_automatic_context(store, paper):
    async def run():
        session = store.list("session", paper["id"])[0]
        assert (
            len(
                bootstrap(
                    {**paper, "title": "Long title " * 1000},
                    {
                        **session,
                        "goal": "G" * 20000,
                        "next_action": "N" * 20000,
                        "pending_question": "Q" * 20000,
                    },
                )
            )
            <= 3000
        )
        store.put(
            "note",
            {"paper_id": paper["id"], "content": "Unrelated note corpus " * 1000},
        )
        coach = Coach(store, FakeRPC)
        body = Send(
            operation_id="long-original",
            content="  Original words\n" * 1000,
            page_index=1,
        )
        sent = await coach.send(paper["id"], body)
        await drained(coach)
        turn = next(p for m, p in coach.rpc.calls if m == "turn/start")
        assert turn["input"][-1]["text"] == body.content
        assert len(turn["input"][0]["text"]) <= 300
        assert "PDF 第 2 页" in turn["input"][0]["text"]
        assert "Repeated quote" not in str(turn) and "Unrelated note corpus" not in str(
            turn
        )
        scope = coach.messages(sent["conversation_id"])[-1]["context_scope"]
        assert scope["notes_included"] == scope["history_messages_included"] == 0
        await coach.close()

    asyncio.run(run())

import asyncio

import pytest
from fastapi.testclient import TestClient

from paper_research_coach.coach import Coach, Send
from paper_research_coach.server import create_app
from paper_research_coach.store import Conflict


class FakeRPC:
    def __init__(self, handler, cwd):
        self.handler = handler
        self.calls = []
        self.responses = []
        self.hold = False

    async def start(self):
        pass

    async def close(self):
        pass

    async def write(self, value):
        self.responses.append(value)

    async def call(self, method, params):
        self.calls.append((method, params))
        if method == "thread/start":
            return {
                "thread": {"id": "native-" + str(len(self.calls))},
                "model": "configured-model",
            }
        if method == "thread/resume":
            return {"thread": {"id": params["threadId"]}}
        if method == "thread/items/list":
            return {
                "data": [
                    {
                        "item": {
                            "type": "agentMessage",
                            "text": "Old answer",
                            "id": "old-a",
                        }
                    },
                    {
                        "item": {
                            "type": "userMessage",
                            "content": [{"type": "text", "text": "Old question"}],
                        }
                    },
                ]
            }
        if method == "turn/start":
            if not self.hold:
                await self.handler(
                    {
                        "method": "item/agentMessage/delta",
                        "params": {
                            "threadId": params["threadId"],
                            "turnId": "turn-1",
                            "itemId": "a",
                            "delta": "回答 $x^2$",
                        },
                    }
                )
                await self.handler(
                    {
                        "method": "turn/completed",
                        "params": {
                            "threadId": params["threadId"],
                            "turn": {"id": "turn-1", "status": "completed"},
                        },
                    }
                )
            return {"turn": {"id": "turn-1"}}
        if method == "turn/interrupt":
            await self.handler(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": params["threadId"],
                        "turn": {"id": params["turnId"], "status": "interrupted"},
                    },
                }
            )
        return {}


async def drained(coach):
    await asyncio.gather(*list(coach.tasks))


def test_send_persists_exact_words_loads_skill_and_deduplicates(store, paper, anchor):
    async def run():
        coach = Coach(store, FakeRPC)
        body = Send(operation_id="once", content="  原话\n不是总结。  ", anchor=anchor)
        result = await coach.send(paper["id"], body)
        assert await coach.send(paper["id"], body) == result
        await drained(coach)
        messages = coach.messages(result["conversation_id"])
        assert messages[0]["content"] == body.content
        assert messages[0]["anchor"] == body.anchor.model_dump(mode="json")
        assert messages[1]["status"] == "completed"
        assert not store.list("note", paper["id"])
        turn = next(p for m, p in coach.rpc.calls if m == "turn/start")
        assert turn["input"][0]["type"] == "skill"
        assert turn["input"][0]["path"].endswith("paper-research-coach/SKILL.md")
        assert turn["input"][1]["text"].endswith(body.content)
        assert paper["source_path"] not in turn["input"][1]["text"]
        with pytest.raises(Conflict):
            await coach.send(
                paper["id"], body.model_copy(update={"content": "不同内容"})
            )
        await coach.send(
            paper["id"],
            Send(
                operation_id="second",
                conversation_id=result["conversation_id"],
                content="继续",
            ),
        )
        await drained(coach)
        assert len([m for m, _ in coach.rpc.calls if m == "thread/start"]) == 1
        await coach.close()

    asyncio.run(run())


def test_note_consent_captures_exact_words_once(store, paper):
    session = store.list("session", paper["id"])[0]
    store.commit(
        {
            "mutations": [
                {
                    "kind": "session",
                    "expected_revision": session["revision"],
                    "data": {**session, "note_consent": True},
                }
            ]
        }
    )

    async def run():
        coach = Coach(store, FakeRPC)
        body = Send(operation_id="consented", content="  直觉\n保留空格。  ")
        await coach.send(paper["id"], body)
        await drained(coach)
        await coach.send(paper["id"], body)
        notes = store.list("note", paper["id"])
        assert len(notes) == 1
        assert notes[0]["content"] == body.content
        assert notes[0]["author"] == "user"
        await coach.close()

    asyncio.run(run())


def test_binding_scopes_conversation_and_version(store, paper, anchor):
    other = store.add_paper("Other")

    async def run():
        coach = Coach(store, FakeRPC)
        conversation = await coach.connect(other["id"])
        with pytest.raises(ValueError):
            await coach.send(
                paper["id"],
                Send(
                    operation_id="wrong",
                    conversation_id=conversation["id"],
                    content="hello",
                ),
            )
        with pytest.raises(Conflict):
            await coach.send(
                paper["id"],
                Send(
                    operation_id="stale",
                    content="hello",
                    anchor={**anchor, "source_version": "old"},
                ),
            )
        with pytest.raises(ValueError):
            coach.snapshot(paper["id"], conversation["id"])

    asyncio.run(run())


def test_stop_busy_turn_and_retains_partial_response(store, paper):
    async def run():
        coach = Coach(store, FakeRPC)
        coach.rpc.hold = True
        sent = await coach.send(paper["id"], Send(operation_id="hold", content="first"))
        for _ in range(100):
            if coach.active[sent["conversation_id"]]["turn_id"]:
                break
            await asyncio.sleep(0.01)
        with pytest.raises(Conflict):
            await coach.send(
                paper["id"], Send(operation_id="duplicate-busy", content="second")
            )
        await coach.handle(
            {
                "method": "item/agentMessage/delta",
                "params": {
                    "threadId": coach.conversation(sent["conversation_id"])[
                        "thread_id"
                    ],
                    "turnId": "turn-1",
                    "itemId": "partial",
                    "delta": "部分回复",
                },
            }
        )
        await coach.stop(sent["conversation_id"])
        await drained(coach)
        answer = coach.messages(sent["conversation_id"])[-1]
        assert answer["status"] == "interrupted"
        assert answer["content"] == "部分回复"
        assert not coach.snapshot(paper["id"])["busy"]

    asyncio.run(run())


def test_restart_preserves_messages_and_resumes_native_thread(store, paper):
    async def run():
        coach = Coach(store, FakeRPC)
        sent = await coach.send(
            paper["id"], Send(operation_id="before", content="First")
        )
        await drained(coach)
        await coach.close()
        restarted = Coach(store, FakeRPC)
        assert restarted.messages(sent["conversation_id"])[0]["content"] == "First"
        await restarted.send(
            paper["id"],
            Send(
                operation_id="after",
                conversation_id=sent["conversation_id"],
                content="Continue",
            ),
        )
        await drained(restarted)
        assert any(m == "thread/resume" for m, _ in restarted.rpc.calls)
        assert not any(m == "thread/start" for m, _ in restarted.rpc.calls)

    asyncio.run(run())


def test_crash_recovery_does_not_resubmit(store, paper):
    coach = Coach(store, FakeRPC)

    async def create():
        c = await coach.connect(paper["id"])
        coach.save_message(
            {
                "id": "unfinished",
                "conversation_id": c["id"],
                "role": "assistant",
                "content": "partial",
                "status": "streaming",
            }
        )
        return c

    c = asyncio.run(create())
    restarted = Coach(store, FakeRPC)
    assert restarted.messages(c["id"])[0]["status"] == "interrupted"
    assert restarted.messages(c["id"])[0]["content"] == "partial"
    assert not restarted.rpc.calls


def test_workbench_tools_are_scoped_and_keep_original_words(store, paper):
    note = store.commit(
        {
            "mutations": [
                {
                    "kind": "note",
                    "data": {
                        "id": "original",
                        "paper_id": paper["id"],
                        "content": "我的原话",
                    },
                }
            ]
        }
    )["records"][0]
    other = store.add_paper("Other")
    foreign = store.commit(
        {
            "mutations": [
                {
                    "kind": "note",
                    "data": {
                        "id": "foreign",
                        "paper_id": other["id"],
                        "content": "another",
                    },
                }
            ]
        }
    )["records"][0]
    coach = Coach(store, FakeRPC)
    state = {
        "conversation": {"paper_id": paper["id"]},
        "answer": {"id": "answer", "conversation_id": "c", "actions": []},
        "stop": False,
    }
    args = {
        "next_action": "检查图2",
        "pending_question": "预算是否一致？",
        "stage": "evidence",
    }
    result = coach.tool_call(state, "prc_next_action", args, "next")
    assert coach.tool_call(state, "prc_next_action", args, "next") == result
    assert store.list("session", paper["id"])[0]["next_action"] == "检查图2"
    coach.tool_call(
        state,
        "prc_comment_note",
        {"note_id": note["id"], "content": "独立评论"},
        "comment",
    )
    assert store.get("note", note["id"])["content"] == "我的原话"
    assert store.get("note", note["id"])["discussed"] is True
    ai = next(n for n in store.list("note", paper["id"]) if n["author"] == "assistant")
    assert ai["links"] == [note["id"]]
    with pytest.raises(ValueError):
        coach.tool_call(
            state,
            "prc_comment_note",
            {"note_id": foreign["id"], "content": "wrong"},
            "bad",
        )
    with pytest.raises(ValueError):
        coach.tool_call(state, "prc_resource", {"name": "../../session-token"}, "path")
    state["stop"] = True
    with pytest.raises(ValueError):
        coach.tool_call(state, "prc_next_action", args, "late")


def test_only_reuses_threads_bound_to_this_paper_and_new_dialogue_is_empty(
    store, paper
):
    async def run():
        coach = Coach(store, FakeRPC)
        other = store.add_paper("Another paper")
        first = await coach.connect(paper["id"])
        first["thread_id"] = "bound-native"
        coach.save_conversation(first)
        coach.save_message(
            {
                "id": "old",
                "conversation_id": first["id"],
                "role": "user",
                "content": "Original question",
                "status": "completed",
            }
        )
        assert (await coach.connect(paper["id"], "bound-native"))["id"] == first["id"]
        with pytest.raises(ValueError, match="当前论文"):
            await coach.connect(other["id"], "bound-native")
        with pytest.raises(ValueError, match="当前论文"):
            await coach.connect(paper["id"], "unrelated-cli")
        fresh = await coach.connect(paper["id"], new=True)
        assert fresh["id"] != first["id"]
        assert coach.messages(fresh["id"]) == []
        assert coach.messages(first["id"])[0]["content"] == "Original question"
        assert not coach.rpc.calls
        with pytest.raises(ValueError):
            coach.snapshot(other["id"], first["id"])

    asyncio.run(run())


def test_conversation_listing_never_reads_global_cli_history(store, paper):
    app = create_app(store, token="test")
    coach = app.state.coach
    coach.rpc = FakeRPC(coach.handle, store.root)
    other = store.add_paper("Another paper")
    first = asyncio.run(coach.connect(paper["id"]))
    asyncio.run(coach.connect(other["id"]))
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        client.headers["Authorization"] = "Bearer test"
        assert client.get("/api/coach/threads").status_code == 422
        listed = client.get(
            "/api/coach/threads", params={"paper_id": paper["id"]}
        ).json()
        assert [c["id"] for c in listed["data"]] == [first["id"]]
        assert not coach.rpc.calls
        assert (
            client.post(
                "/api/coach/active",
                json={"paper_id": other["id"], "conversation_id": first["id"]},
            ).status_code
            == 400
        )


def test_chat_api_requires_local_credentials_and_saves_exact_messages(store, paper):
    app = create_app(store, token="test")
    app.state.coach.rpc = FakeRPC(app.state.coach.handle, store.root)
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        assert client.get("/api/coach/conversation/" + paper["id"]).status_code == 401
        client.headers["Authorization"] = "Bearer test"
        sent = client.post(
            "/api/coach/send/" + paper["id"],
            json={"operation_id": "api", "content": "  exact\n原话  "},
        ).json()
        snapshot = client.get("/api/coach/conversation/" + paper["id"]).json()
        assert snapshot["messages"][0]["content"] == "  exact\n原话  "
        path = (
            "/api/coach/save-message/"
            + sent["conversation_id"]
            + "/"
            + sent["message_id"]
        )
        note = client.post(path, json={}).json()
        assert note["content"] == "  exact\n原话  "
        assert client.post(path, json={}).json() == note
        assert (
            client.post("/api/coach/active", json={"paper_id": paper["id"]}).status_code
            == 200
        )
        assert store.setting("active-paper") == paper["id"]


def test_cli_uses_the_conversation_selected_in_the_workbench(store, paper):
    async def run():
        coach = Coach(store, FakeRPC)
        first = await coach.connect(paper["id"])
        await coach.connect(paper["id"], new=True)
        store.set_setting("coach-current:" + paper["id"], first["id"])
        sent = await coach.send(
            paper["id"],
            Send(operation_id="shared-selection", content="CLI continuation"),
        )
        assert sent["conversation_id"] == first["id"]
        await drained(coach)

    asyncio.run(run())


def test_provider_change_keeps_dialogue_and_loads_skill_in_new_native_thread(
    store, paper
):
    async def run():
        coach = Coach(store, FakeRPC)
        sent = await coach.send(
            paper["id"],
            Send(operation_id="before-provider", content="Keep this thought"),
        )
        await drained(coach)
        conversation = coach.conversation(sent["conversation_id"])
        old_thread = conversation["thread_id"]
        conversation["model_provider"] = "previous-provider"
        coach.save_conversation(conversation)
        coach.resumed.clear()
        again = await coach.send(
            paper["id"],
            Send(
                operation_id="after-provider",
                conversation_id=conversation["id"],
                content="Continue",
            ),
        )
        await drained(coach)
        assert again["conversation_id"] == sent["conversation_id"]
        new = coach.conversation(conversation["id"])
        assert new["thread_id"] != old_thread
        assert new["previous_thread_ids"] == [old_thread]
        turn = [p for m, p in coach.rpc.calls if m == "turn/start"][-1]
        assert turn["input"][0]["type"] == "skill"
        assert "Keep this thought" in turn["input"][1]["text"]

    asyncio.run(run())


def test_authorized_original_note_survives_cli_connection_failure(store, paper):
    session = store.list("session", paper["id"])[0]
    store.commit(
        {
            "mutations": [
                {
                    "kind": "session",
                    "expected_revision": session["revision"],
                    "data": {**session, "note_consent": True},
                }
            ]
        }
    )

    class Offline(FakeRPC):
        async def start(self):
            raise ValueError("offline")

    async def run():
        coach = Coach(store, Offline)
        sent = await coach.send(
            paper["id"],
            Send(operation_id="offline-original", content="  Keep exactly\nthis.  "),
        )
        assert (
            store.list("note", paper["id"])[0]["content"] == "  Keep exactly\nthis.  "
        )
        await drained(coach)
        assert coach.messages(sent["conversation_id"])[-1]["status"] == "failed"

    asyncio.run(run())

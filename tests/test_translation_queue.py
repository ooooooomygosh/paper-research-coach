import asyncio
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from paper_research_coach.codex_text import CodexText
from paper_research_coach.server import create_app
from paper_research_coach.translation import (
    Translation,
    TranslationBatch,
    TranslationRequest,
)


class RPC:
    async def start(self):
        pass

    async def call(self, method, params):
        if method == "model/list":
            return {
                "data": [
                    {
                        "model": "gpt-6-luna",
                        "supportedReasoningEfforts": [{"reasoningEffort": "low"}],
                    }
                ]
            }
        return {"config": {}}


def test_parallel_papers_multiplexed_requests_and_pdf_ready_before_alignment(
    store, paper, monkeypatch, tmp_path
):
    # A real subprocess sends requests before receiving any reply. It rejects
    # misrouted responses, then holds alignment while the PDFs are downloaded.
    script = tmp_path / "worker.py"
    script.write_text("""import json,sys,shutil
from pathlib import Path
c=json.loads(sys.stdin.readline())
for i in range(6):
 print(json.dumps({"type":"translate","request_id":i,"text":f"request-{i}"}),flush=True)
for i in range(6):
 r=json.loads(sys.stdin.readline())
 assert r["text"]==f"translated-request-{r['request_id']}",r
d=Path(c["output_dir"])
for kind in ("mono","dual"): shutil.copyfile(c["source_path"],d/f"{kind}.pdf")
(d/"mapping.json").write_text(json.dumps({"segments":[{"id":"s","translated":True,"source":{"text":"First result. Second result.","page_index":0,"rects":[]},"target":{"text":"第一个结果。第二个结果。","page_index":0,"rects":[]},"links":[]}]}))
print(json.dumps({"type":"finish",**{k:str(d/("mapping.json" if k=="mapping" else k+".pdf")) for k in ("mono","dual","mapping")}}),flush=True)
""")
    original_exec = asyncio.create_subprocess_exec

    async def worker(*args, **kwargs):
        return await original_exec(sys.executable, "-u", str(script), **kwargs)

    monkeypatch.setattr(
        "paper_research_coach.translation.asyncio.create_subprocess_exec", worker
    )

    async def run():
        release = asyncio.Event()
        active, peak, prompts = 0, 0, []

        class Engine:
            def __init__(self, *args):
                self.rpc = RPC()

            async def text(self, prompt, schema=None, **kwargs):
                nonlocal active, peak
                active += 1
                peak = max(peak, active)
                prompts.append(prompt)
                try:
                    if schema:
                        await release.wait()
                        return json.dumps(
                            {
                                "links": [
                                    {
                                        "source_ids": [0, 1],
                                        "target_ids": [0, 1],
                                        "uncertain": False,
                                    }
                                ]
                            }
                        )
                    await asyncio.sleep(0.01 * (6 - int(prompt[-1])))
                    return "translated-" + prompt
                finally:
                    active -= 1

            async def close(self):
                pass

        trans = Translation(store, Engine)
        monkeypatch.setattr(trans, "interpreter", lambda: sys.executable)
        other_papers = []
        for title in ("Second", "Third"):
            path = tmp_path / f"{title}.pdf"
            path.write_bytes(
                Path(paper["source_path"]).read_bytes() + f"\n%{title}\n".encode()
            )
            other_papers.append(store.add_paper(title, str(path)))
        second, third = other_papers
        jobs = [
            await trans.create(
                p["id"],
                TranslationRequest(
                    operation_id=p["id"], source_version=p["source_version"]
                ),
            )
            for p in (paper, second, third)
        ]
        try:
            for _ in range(400):
                if all(trans.public(trans.job(j["id"]))["pdf_ready"] for j in jobs[:2]):
                    break
                await asyncio.sleep(0.01)
            assert all(trans.job(j["id"])["state"] == "running" for j in jobs[:2])
            assert trans.job(jobs[2]["id"])["state"] == "queued"
            assert trans.running_papers == 2 and 1 < peak <= 4
            assert trans.artifact(jobs[0]["id"], "dual").is_file()
            assert trans.public(trans.job(jobs[0]["id"]))["pdf_ready"]
            await trans.stop(jobs[2]["id"])
            release.set()
            await asyncio.gather(*list(trans.tasks.values()))
            assert all(trans.job(j["id"])["state"] == "completed" for j in jobs[:2])
            assert trans.job(jobs[2]["id"])["state"] == "cancelled"
            assert len(prompts) == 14
        finally:
            release.set()
            await trans.close()

    asyncio.run(run())


def test_batch_reuses_jobs_and_recovers_queue_without_restarting_cancelled_work(
    store, paper, monkeypatch
):
    async def run():
        trans = Translation(store)
        monkeypatch.setattr(trans, "interpreter", lambda: sys.executable)

        async def hold(job):
            await asyncio.Event().wait()

        monkeypatch.setattr(trans, "run", hold)
        request = TranslationBatch(
            operation_id="batch",
            papers=[
                {"paper_id": paper["id"], "source_version": paper["source_version"]}
            ]
            * 2,
        )
        result = await trans.batch(request)
        first = result["data"][0]["job"]
        assert len(result["data"]) == 1
        assert (await trans.batch(request))["data"][0]["job"]["id"] == first["id"]
        assert len(trans.jobs()) == 1
        await trans.close()
        restarted = Translation(store)
        seen = []

        async def resumed(job):
            seen.append(job["id"])
            await asyncio.Event().wait()

        monkeypatch.setattr(restarted, "run", resumed)
        await restarted.resume()
        await asyncio.sleep(0)
        assert seen == [first["id"]]
        await restarted.stop(first["id"])
        await restarted.close()
        final = Translation(store)
        await final.resume()
        assert not final.tasks and final.job(first["id"])["state"] == "cancelled"
        await final.close()

    asyncio.run(run())


def test_queue_auth_bounds_and_partial_batch_errors(store, paper, monkeypatch):
    app = create_app(store, token="private")
    trans = app.state.translation
    monkeypatch.setattr(trans, "interpreter", lambda: sys.executable)
    monkeypatch.setattr(trans, "schedule", lambda job: None)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        auth = {"Authorization": "Bearer private"}
        assert client.get("/api/translation/jobs").status_code == 401
        assert client.post("/api/translation/batch", json={}).status_code == 401
        assert (
            client.post(
                "/api/translation/settings", json={"paper_concurrency": 5}, headers=auth
            ).status_code
            == 422
        )
        response = client.post(
            "/api/translation/batch",
            headers=auth,
            json={
                "operation_id": "bulk",
                "papers": [
                    {
                        "paper_id": paper["id"],
                        "source_version": paper["source_version"],
                    },
                    {"paper_id": "missing", "source_version": "old"},
                ],
            },
        ).json()
        assert [r["outcome"] for r in response["data"]] == ["queued", "error"]
        assert (
            len(client.get("/api/translation/jobs", headers=auth).json()["data"]) == 1
        )


def test_codex_parallel_threads_route_out_of_order_and_cancel_independently(tmp_path):
    class MultiplexRPC:
        def __init__(self, handler, cwd):
            self.handler, self.cwd = handler, cwd
            self.sequence, self.turns, self.interrupted = 0, {}, []

        async def start(self):
            pass

        async def call(self, method, params):
            if method == "thread/start":
                self.sequence += 1
                assert params["ephemeral"] and params["dynamicTools"] == []
                return {"thread": {"id": str(self.sequence)}}
            if method == "turn/start":
                self.turns[params["threadId"]] = params["input"][0]["text"]
                return {"turn": {"id": "turn-" + params["threadId"]}}
            if method == "turn/interrupt":
                self.interrupted.append(params["threadId"])
            return {"config": {}}

        async def close(self):
            pass

    async def run():
        engine = CodexText(tmp_path, "gpt-6-luna", rpc_factory=MultiplexRPC)
        first = asyncio.create_task(engine.text("first"))
        second = asyncio.create_task(engine.text("second"))
        for _ in range(10):
            if len(engine.rpc.turns) == 2:
                break
            await asyncio.sleep(0)
        assert len(engine.rpc.turns) == 2
        second_id = next(k for k, v in engine.rpc.turns.items() if v == "second")
        await engine.handle(
            {
                "method": "item/completed",
                "params": {
                    "threadId": second_id,
                    "item": {"type": "agentMessage", "id": "m", "text": "第二个"},
                },
            }
        )
        await engine.handle(
            {
                "method": "turn/completed",
                "params": {"threadId": second_id, "turn": {"status": "completed"}},
            }
        )
        assert await second == "第二个" and not first.done()
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert len(engine.rpc.interrupted) == 1 and not engine.active
        await engine.close()

    asyncio.run(run())


def test_live_request_limit_changes_and_duplicate_cache_requests(store, paper):
    async def run():
        trans = Translation(store)
        trans.settings({"request_concurrency": 1})
        release = asyncio.Event()
        started = []

        class Engine:
            async def text(self, prompt, **kwargs):
                started.append(prompt)
                await release.wait()
                return "translated-" + prompt

        engine = Engine()
        job = {
            "paper_id": paper["id"],
            "source_version": paper["source_version"],
            "model": "gpt-6-luna",
        }
        first = asyncio.create_task(trans.cached_text(engine, job, "a"))
        duplicate = asyncio.create_task(trans.cached_text(engine, job, "a"))
        second = asyncio.create_task(trans.cached_text(engine, job, "b"))
        await asyncio.sleep(0.01)
        assert started == ["a"]
        trans.settings({"request_concurrency": 2})
        await asyncio.sleep(0.01)
        assert started == ["a", "b"] and trans.running_requests == 2
        trans.settings({"request_concurrency": 1})
        third = asyncio.create_task(trans.cached_text(engine, job, "c"))
        await asyncio.sleep(0.01)
        assert len(started) == 2
        release.set()
        values = await asyncio.gather(first, duplicate, second, third)
        assert values == [
            "translated-a",
            "translated-a",
            "translated-b",
            "translated-c",
        ]
        assert started == ["a", "b", "c"] and trans.running_requests == 0
        await trans.close()

    asyncio.run(run())


def test_bilingual_badge_checks_replaced_source_and_reuses_unchanged_source_checks(
    store, paper, monkeypatch
):
    trans = Translation(store)
    directory = store.root / "translations" / "ready"
    directory.mkdir(parents=True)
    paths = {
        k: str(directory / ("mapping.json" if k == "mapping" else k + ".pdf"))
        for k in ("mono", "dual", "mapping")
    }
    for path in paths.values():
        Path(path).write_text("fixture")
    job = {
        "id": "ready",
        "paper_id": paper["id"],
        "source_version": paper["source_version"],
        "state": "running",
        "artifacts": paths,
    }
    original = store.check_source
    calls = []

    def check(paper_id):
        calls.append(paper_id)
        return original(paper_id)

    monkeypatch.setattr(store, "check_source", check)
    assert trans.public(job)["pdf_ready"]
    assert trans.public(job)["pdf_ready"] and len(calls) == 1
    source = Path(paper["source_path"])
    source.write_bytes(source.read_bytes() + b"\n% replaced source\n")
    assert not trans.public(job)["current"]
    assert not trans.public(job)["pdf_ready"] and len(calls) == 2

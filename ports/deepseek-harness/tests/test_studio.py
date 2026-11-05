import asyncio
import json
import re

import httpx
import pytest

from paper_research_coach.server import create_app
from paper_research_coach.store import Store
from paper_research_coach.workspaces import artifact_document


async def render(payload):
    # Test renderer fixture. Production renders through the actual Node bridge,
    # covered by tests/studio.test.mjs and the live integration test.
    if "BAD" in payload["source"]:
        raise ValueError("invalid draft")
    return {"html": '<html><head><meta http-equiv="Content-Security-Policy" content="script-src \'sha256-existing\'"></head><body><p>Test renderer fixture</p></body></html>',
            "warnings": [], "meta": {"title": "Fixture explanation"}}


class Text:
    closed = 0
    prompts = []
    wait = False

    def __init__(self, *args):
        pass

    async def text(self, prompt, **kwargs):
        self.prompts.append(prompt)
        if self.wait:
            await asyncio.sleep(60)
        return "---\ntitle: Fixture\n---\n## A Evidence\nThe source supports a limited conclusion."

    async def close(self):
        Text.closed += 1


def test_artifact_state_cannot_end_the_trusted_bootstrap_or_grant_untrusted_scripts():
    raw = '<html><head><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'sha256-original\'"></head><body><script>untrusted()</script></body></html>'
    result = artifact_document(raw, item_id="studio-test", kind="studio", storage={"note": "</script><script>evil()</script>"})
    policy = re.search(r'Content-Security-Policy" content="([^"]+)', result)[1]
    assert "'sha256-original'" in policy
    assert len(re.findall("sha256-", policy)) == 2
    assert "\\u003c/script" in result
    assert "<script>evil()" not in result


def test_studio_publishes_atomically_retains_versions_and_reader_state(tmp_path):
    async def run():
        app = create_app(Store(tmp_path), "secret", workspace_text_factory=Text, workspace_renderer=render)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1", headers={"authorization": "Bearer secret"}) as client:
            doc = (await client.post("/api/workspace/studios", json={"source": "valid source"})).json()
            url = "/api/workspace/studios/" + doc["id"]
            published = (await client.post(url + "/render")).json()
            first = published["published"]["version"]
            await client.put("/api/workspace/storage/studio/" + doc["id"], json={"key": "am-reply", "value": "my own answer"})
            await client.put(url, json={"source": "BAD"})
            assert (await client.post(url + "/render")).status_code == 400
            preserved = (await client.get(url)).json()
            assert preserved["published"]["version"] == first
            view = await client.get("/api/workspace/view/studio/" + doc["id"])
            assert view.status_code == 200 and "my own answer" in view.text
            assert "sandbox" in view.headers["content-security-policy"] and "allow-same-origin" not in view.headers["content-security-policy"]
            await client.put(url, json={"source": "revised source"})
            second = (await client.post(url + "/render")).json()
            assert second["published"]["version"] != first
            assert second["history"][0]["version"] == first
            assert (await client.get("/api/workspace/view/studio/" + doc["id"], params={"version": first})).status_code == 200
            assert (await client.get("/api/workspace/export/studio/" + doc["id"] + "/page.md")).text == "revised source"
            assert (await client.get("/api/workspace/export/studio/" + doc["id"] + "/private.sqlite")).status_code == 400
        await app.state.workspace.close()
    asyncio.run(run())


def test_generation_and_stop_close_the_account_client_and_keep_saved_work(tmp_path):
    async def run():
        app = create_app(Store(tmp_path), "secret", workspace_text_factory=Text, workspace_renderer=render)
        workspace = app.state.workspace
        doc = workspace.studio.create({"question": "Explain a bounded conclusion"})
        job = workspace.studio.generate(doc["id"], {})
        await workspace.jobs.tasks[job["id"]]
        assert workspace.store.get("job", job["id"])["state"] == "completed"
        version = workspace.store.get("studio", doc["id"])["published"]["version"]
        Text.wait = True
        try:
            pending = workspace.studio.generate(doc["id"], {"question": "A follow-up"})
            await asyncio.sleep(0.02)
            stopped = await workspace.jobs.cancel(pending["id"])
            assert stopped["state"] == "cancelled"
            assert workspace.store.get("studio", doc["id"])["published"]["version"] == version
            assert Text.closed >= 2
        finally:
            Text.wait = False
            await workspace.close()
    asyncio.run(run())

import json
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from paper_research_coach import launcher


def transport(monkeypatch, handler):
    client = httpx.Client
    monkeypatch.setattr(
        launcher.httpx,
        "Client",
        lambda **kwargs: client(**kwargs, transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setattr(launcher, "session_token", lambda store: "test-token")


def test_reuses_running_service_and_opens_private_paper_link(monkeypatch, store, paper):
    calls, opened = [], []

    def handler(request):
        assert request.headers["authorization"] == "Bearer test-token"
        calls.append((request.url.path, json.loads(request.content or b"{}")))
        if request.url.path == "/api/state":
            return httpx.Response(200, json={"papers": [paper]})
        return httpx.Response(200, json={"id": "selected"})

    transport(monkeypatch, handler)
    monkeypatch.setattr(
        launcher.subprocess, "Popen", lambda *a, **k: pytest.fail("duplicate server")
    )
    monkeypatch.setattr(
        launcher.webbrowser, "open", lambda url: opened.append(url) or True
    )
    result = launcher.open_workbench(store, paper_id=paper["id"], new=True)
    assert result == {
        "opened": True,
        "paper_id": paper["id"],
        "conversation_id": "selected",
    }
    params = parse_qs(urlsplit(opened[0]).fragment)
    assert params == {
        "token": ["test-token"],
        "paper": [paper["id"]],
        "conversation": ["selected"],
    }
    assert ("/api/coach/connect/" + paper["id"], {"new": True}) in calls
    assert "test-token" not in json.dumps(result)


def test_starts_missing_service_once_and_reuses_on_next_open(monkeypatch, store):
    spawned = []

    def handler(request):
        if not spawned:
            raise httpx.ConnectError("not running", request=request)
        return httpx.Response(200, json={"papers": []})

    transport(monkeypatch, handler)
    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        lambda args, **kwargs: spawned.append((args, kwargs)),
    )
    monkeypatch.setattr(launcher.webbrowser, "open", lambda url: True)
    launcher.open_workbench(store)
    launcher.open_workbench(store)
    assert len(spawned) == 1
    assert "--no-open" in spawned[0][0]
    assert str(store.root) in spawned[0][0]
    assert spawned[0][1]["start_new_session"] is True


@pytest.mark.parametrize("status,payload", [(401, {}), (200, [])])
def test_other_service_cannot_receive_a_private_launch_link(
    monkeypatch, store, status, payload
):
    transport(monkeypatch, lambda request: httpx.Response(status, json=payload))
    monkeypatch.setattr(
        launcher.subprocess, "Popen", lambda *a, **k: pytest.fail("must not start")
    )
    monkeypatch.setattr(
        launcher.webbrowser, "open", lambda url: pytest.fail("must not disclose link")
    )
    with pytest.raises(ValueError, match="另一处服务"):
        launcher.open_workbench(store)

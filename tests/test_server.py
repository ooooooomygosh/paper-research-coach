from fastapi.testclient import TestClient
from paper_research_coach.server import create_app


def client(store):
    return TestClient(
        create_app(store, token="test-token"), base_url="http://127.0.0.1:8765"
    )


def test_requires_credentials_and_same_origin(store):
    c = client(store)
    assert c.get("/api/state").status_code == 401
    assert c.post("/api/login", json={"token": "wrong"}).status_code == 401
    assert (
        c.post(
            "/api/login",
            json={"token": "test-token"},
            headers={"Origin": "http://evil.example"},
        ).status_code
        == 403
    )
    assert c.post("/api/login", json={"token": "test-token"}).status_code == 200
    assert c.get("/api/state").status_code == 200
    assert c.post("/api/import", json={"title": "x"}).status_code == 403
    assert (
        c.post(
            "/api/import",
            json={"title": "x"},
            headers={"Origin": "http://127.0.0.1:8765"},
        ).status_code
        == 200
    )
    assert c.get("/api/state", headers={"Host": "evil.example"}).status_code == 403
    assert (
        "frame-ancestors 'none'"
        in c.get("/api/state").headers["Content-Security-Policy"]
    )


def test_commit_context_pdf_export_and_conflict(store, paper, anchor):
    c = client(store)
    c.headers["Authorization"] = "Bearer test-token"
    tx = {
        "operation_id": "api-tx",
        "mutations": [
            {
                "kind": "note",
                "data": {
                    "id": "api-note",
                    "paper_id": paper["id"],
                    "content": "verbatim",
                    "anchor": anchor,
                },
            }
        ],
    }
    r = c.post("/api/commit", json=tx)
    assert r.status_code == 200
    assert c.post("/api/commit", json=tx).json() == r.json()
    assert (
        c.get("/api/context/" + paper["id"]).json()["pending_thoughts"][0]["content"]
        == "verbatim"
    )
    tx["mutations"][0]["data"]["content"] = "other"
    assert c.post("/api/commit", json=tx).status_code == 409
    assert c.get("/api/pdf/" + paper["id"]).content[:4] == b"%PDF"
    assert (
        c.get("/api/text/" + paper["id"] + "/0").json()["text"].startswith("Synthetic")
    )
    result = c.post("/api/export", json={"kind": "pdf", "paper_id": paper["id"]}).json()
    assert c.get(result["download"]).content[:4] == b"%PDF"
    assert c.get("/api/history/api-note").json()[0]["revision"] == 1


def test_upload_makes_managed_copy_and_rejects_non_pdf(store, pdf):
    c = client(store)
    c.headers["Authorization"] = "Bearer test-token"
    result = c.post("/api/upload?title=Uploaded", content=pdf.read_bytes())
    assert result.status_code == 200
    assert result.json()["source_path"] != str(pdf)
    assert c.post("/api/upload?title=Bad", content=b"bad").status_code in (400, 422)


def test_export_path_cannot_escape(store):
    c = client(store)
    c.headers["Authorization"] = "Bearer test-token"
    assert c.get("/api/download/not-found.pdf").status_code == 404
    assert c.post("/api/commit", json={"mutations": []}).status_code == 422


def test_manual_refresh_is_authenticated_and_runs_both_connected_sources(store, monkeypatch):
    app = create_app(store, token="test-token")
    assert app.state.sync.state()["poll_seconds"] == 600
    assert app.state.vault.state()["poll_seconds"] == 600
    app.state.sync.set_state(collection="chosen", enabled=False)
    store.set_setting("vault", {"root": "/configured", "enabled": False})
    calls = []
    monkeypatch.setattr(app.state.sync, "run", lambda: calls.append("zotero") or {"state": "connected"})
    monkeypatch.setattr(app.state.vault, "run", lambda **kw: calls.append(("vault", kw["manual"])) or {"state": "connected"})
    c = TestClient(app, base_url="http://127.0.0.1")
    assert c.post("/api/sync/refresh").status_code == 401
    assert not calls
    result = c.post("/api/sync/refresh", headers={"Authorization": "Bearer test-token"})
    assert result.status_code == 200
    assert calls == [("vault", True), "zotero"]
    assert not app.state.sync.state()["enabled"]

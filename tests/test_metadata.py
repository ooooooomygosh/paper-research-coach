import json

import httpx
import pytest
from reportlab.pdfgen import canvas

from paper_research_coach.metadata import (
    MetadataResolver,
    MetadataPending,
    crossref_payload,
)


def publication():
    return {
        "type": "journal-article",
        "title": ["A synthetic title about scientific evidence"],
        "DOI": "10.1234/synthetic",
        "author": [
            {"given": "Ada", "family": "Example"},
            {"given": "Bo", "family": "Test"},
            {"name": "Synthetic Research Group"},
        ],
        "container-title": ["Synthetic Journal"],
        "published": {"date-parts": [[2026, 9]]},
    }


def source(store, tmp_path):
    path = tmp_path / "metadata.pdf"
    c = canvas.Canvas(str(path))
    c.drawString(40, 780, publication()["title"][0])
    c.drawString(40, 755, "Ada Example, Bo Test, Synthetic Research Group")
    c.drawString(40, 730, "Abstract: synthetic content. DOI 10.1234/synthetic")
    c.save()
    return store.add_paper(publication()["title"][0], str(path))


def test_structured_creators_and_verified_pdf_cache(store, tmp_path):
    p = source(store, tmp_path)
    calls = []

    def respond(r):
        calls.append(r)
        return httpx.Response(200, json={"message": publication()})

    resolver = MetadataResolver(
        store, httpx.Client(transport=httpx.MockTransport(respond))
    )
    result = resolver.resolve(p)
    assert (
        result["source_version"] == p["source_version"]
        and len(result["payload"]["creators"]) == 3
    )
    assert result["payload"]["creators"][0]["lastName"] == "Example"
    assert result["payload"]["creators"][2]["name"] == "Synthetic Research Group"
    assert resolver.resolve(p) == result and len(calls) == 1


def test_wrong_doi_and_unverified_authors_do_not_pass(store, tmp_path, monkeypatch):
    p = source(store, tmp_path)
    p["authors"] = "Ada Example et al."
    data = publication() | {
        "title": ["An unrelated publication with the wrong identifier"]
    }
    resolver = MetadataResolver(
        store,
        httpx.Client(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, json={"message": data})
            )
        ),
    )
    monkeypatch.setattr(resolver, "openalex", lambda query: [])
    with pytest.raises(MetadataPending):
        resolver.resolve(p)
    assert store.setting("bibliography:" + p["id"])["status"] == "pending"


def test_pdf_changes_during_lookup_never_verified(store, tmp_path):
    p = source(store, tmp_path)

    def respond(r):
        with open(p["source_path"], "ab") as f:
            f.write(b"\n% changed")
        return httpx.Response(200, json={"message": publication()})

    resolver = MetadataResolver(
        store, httpx.Client(transport=httpx.MockTransport(respond))
    )
    with pytest.raises(MetadataPending):
        resolver.resolve(p)
    assert store.setting("bibliography:" + p["id"]) is None


def test_openalex_errors_do_not_persist_credentials(store, tmp_path, monkeypatch):
    import keyring

    p = source(store, tmp_path)
    secret = "FAKE_METADATA_SECRET_ONLY"
    monkeypatch.setattr(keyring, "get_password", lambda *a: secret)

    def fail(r):
        if "openalex" in r.url.host:
            assert r.url.params["api_key"] == secret
            raise httpx.ConnectError(str(r.url), request=r)
        return httpx.Response(404, json={})

    resolver = MetadataResolver(
        store, httpx.Client(transport=httpx.MockTransport(fail))
    )
    with pytest.raises(MetadataPending) as caught:
        resolver.resolve(p)
    assert secret not in str(caught.value)
    assert secret not in json.dumps(store.setting("bibliography:" + p["id"]))

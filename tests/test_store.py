import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest
from pypdf import PdfWriter
from paper_research_coach.models import Anchor
from paper_research_coach.store import Conflict, Store, digest
from paper_research_coach.exports import (
    annotated_pdf,
    export,
    import_markdown,
    comparison_csv,
)


def test_exact_words_atomic_retry_and_persistence(store, paper):
    words = "  我觉得…\n这个机制可能不成立。\n  <script>不是命令</script>  "
    payload = {
        "operation_id": "same",
        "mutations": [
            {
                "kind": "note",
                "data": {"id": "raw", "paper_id": paper["id"], "content": words},
            },
            {
                "kind": "note",
                "data": {
                    "id": "ai",
                    "paper_id": paper["id"],
                    "author": "assistant",
                    "provenance": "INFERENCE",
                    "content": "另一种解释",
                    "links": ["raw"],
                },
            },
        ],
    }
    result = store.commit(payload)
    assert store.commit(payload) == result
    assert len(store.list("note")) == 2
    assert Store(store.root).get("note", "raw")["content"] == words
    bad = json.loads(json.dumps(payload))
    bad["mutations"][0]["data"]["content"] = "different"
    with pytest.raises(Conflict):
        store.commit(bad)
    assert len(store.history("raw")) == 1
    bad = {
        "mutations": [
            {
                "kind": "note",
                "data": {"id": "rollback", "paper_id": paper["id"], "content": "x"},
            },
            {
                "kind": "note",
                "data": {"id": "fail", "paper_id": "missing", "content": "x"},
            },
        ]
    }
    with pytest.raises(ValueError):
        store.commit(bad)
    with pytest.raises(KeyError):
        store.get("note", "rollback")


def test_concurrent_edits_have_one_winner(store, paper):
    n = store.put("note", {"id": "n", "paper_id": paper["id"], "content": "original"})

    def edit(text):
        try:
            return store.put("note", n | {"content": text}, 1)
        except Conflict:
            return None

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(edit, ["first", "second"]))
    assert sum(x is not None for x in results) == 1
    assert [h["data"]["content"] for h in store.history("n")][0] == "original"


def test_authorship_readonly_anchor_boundaries(store, paper, anchor):
    n = store.put("note", {"paper_id": paper["id"], "content": "exact"})
    with pytest.raises(Conflict):
        store.put("note", n | {"author": "assistant", "provenance": "INFERENCE"}, 1)
    with pytest.raises(ValueError):
        store.put(
            "note",
            {
                "paper_id": paper["id"],
                "author": "assistant",
                "provenance": "USER",
                "content": "not learner",
            },
        )
    with pytest.raises(ValueError):
        store.put(
            "note",
            {
                "paper_id": paper["id"],
                "content": "x",
                "anchor": anchor | {"source_version": "wrong"},
            },
        )
    with pytest.raises(ValueError):
        store.put(
            "note",
            {
                "paper_id": paper["id"],
                "content": "x",
                "anchor": anchor | {"page_index": 10},
            },
        )
    with pytest.raises(ValueError):
        Anchor.model_validate(anchor | {"rects": [[1, 2, float("nan"), 4]]})
    n = store.put(
        "note", {"paper_id": paper["id"], "content": "external", "read_only": True}
    )
    with pytest.raises(Conflict):
        store.put("note", n | {"content": "lost"}, 1)


def test_version_change_retains_history_and_stales_positions(
    store, paper, anchor, tmp_path
):
    n = store.put(
        "note",
        {
            "paper_id": paper["id"],
            "content": "original",
            "anchor": anchor | {"page_index": 1},
        },
    )
    old = paper["source_version"]
    new = tmp_path / "new.pdf"
    w = PdfWriter()
    w.add_blank_page(600, 800)
    w.write(new)
    changed = store.replace_source(paper["id"], str(new))
    assert changed["source_version"] != old
    n = store.get("note", n["id"])
    assert n["anchor"]["status"] == "stale"
    assert n["anchor"]["source_version"] == old
    n = store.put("note", n | {"discussed": True}, n["revision"])
    assert len(store.history(n["id"])) == 3
    new.write_bytes(b"changed externally")
    assert store.check_source(paper["id"])["status"] == "changed"
    with pytest.raises(ValueError):
        annotated_pdf(store, paper["id"], tmp_path / "no.pdf")


def test_pdf_export_geometry_and_no_raw_mutation(store, paper, anchor, pdf, tmp_path):
    from pypdf import PdfReader

    original = digest(pdf)
    store.put(
        "note", {"paper_id": paper["id"], "content": "我的原话", "anchor": anchor}
    )
    unresolved = store.put("note", {"paper_id": paper["id"], "content": "not placed"})
    result = annotated_pdf(store, paper["id"], tmp_path / "annotated.pdf")
    assert result["unplaced_note_ids"] == [unresolved["id"]]
    annotation = PdfReader(result["path"]).pages[0]["/Annots"][0].get_object()
    assert list(annotation["/Rect"]) == [60, 675, 230, 695]
    assert list(annotation["/QuadPoints"]) == [60, 695, 230, 695, 60, 675, 230, 675]
    assert "我的原话" in annotation["/Contents"]
    assert digest(pdf) == original
    with pytest.raises(ValueError):
        annotated_pdf(store, paper["id"], pdf)
    with pytest.raises(FileExistsError):
        annotated_pdf(store, paper["id"], tmp_path / "annotated.pdf")


def test_markdown_import_is_atomic_idempotent_and_preserves_exact_words(
    store, paper, tmp_path
):
    md = tmp_path / "notes.md"
    words = "  第一行\n第二行  "
    md.write_text(
        '<!-- prc-note {"id":"m1"} -->\n' + words + "\n<!-- /prc-note -->",
        encoding="utf8",
    )
    assert import_markdown(store, paper["id"], str(md)) == {"imported": 1}
    assert store.get("note", "m1")["content"] == words
    assert import_markdown(store, paper["id"], str(md)) == {"imported": 0}
    md.write_text(
        '<!-- prc-note {"id":"m2"} -->\nnew\n<!-- /prc-note -->\n<!-- prc-note {"id":"m1"} -->\nconflict\n<!-- /prc-note -->'
    )
    with pytest.raises(ValueError):
        import_markdown(store, paper["id"], str(md))
    with pytest.raises(KeyError):
        store.get("note", "m2")
    result = export(store, "paper", paper["id"])
    assert words in open(result["path"]).read()


def test_review_records_assistance_and_uses_editable_intervals(store, paper):
    r = store.put(
        "review",
        {
            "paper_id": paper["id"],
            "prompt": "Explain the mechanism",
            "intervals": [2, 5],
        },
    )
    r = store.review_answer(r["id"], "my first answer", "none", True, r["revision"])
    assert r["interval_index"] == 1
    assert (
        1.99
        < (
            datetime.fromisoformat(r["due_at"]) - datetime.now(timezone.utc)
        ).total_seconds()
        / 86400
        < 2.01
    )
    r = store.review_answer(
        r["id"], "needed explanation", "worked", True, r["revision"]
    )
    assert r["interval_index"] == 0 and len(r["attempts"]) == 2
    with pytest.raises(Conflict):
        store.review_answer(r["id"], "retry", "none", True, 1)
    with pytest.raises(ValueError):
        store.put(
            "review", {"paper_id": paper["id"], "prompt": "bad", "intervals": [0]}
        )


def test_comparison_csv_escapes_formulas_and_relations_require_two_papers(store, paper):
    store.put("paper", paper | {"title": "=BAD()"}, paper["revision"])
    assert "'=BAD()" in comparison_csv(store)
    with pytest.raises(ValueError):
        store.put("relation", {"paper_id": paper["id"], "target_id": paper["id"]})


def test_duplicate_pdf_does_not_cross_zotero_instances(store, pdf):
    a = store.add_paper("A", str(pdf), zotero_server="instance-a", zotero_key="A")
    b = store.add_paper("B", str(pdf), zotero_server="instance-b", zotero_key="A")
    assert a["id"] != b["id"]
    assert (
        store.add_paper("again", str(pdf), zotero_server="instance-b", zotero_key="A")[
            "id"
        ]
        == b["id"]
    )

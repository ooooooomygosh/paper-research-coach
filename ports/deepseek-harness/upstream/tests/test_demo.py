from pathlib import Path

import pytest
from pypdf import PdfReader

from paper_research_coach.demo import prepare_demo, serve_demo, parser
from paper_research_coach.runtime_prompt import RULES, bootstrap


def test_demo_is_searchable_explicitly_synthetic_and_does_not_grant_consent(tmp_path):
    store, paper = prepare_demo(tmp_path / "demo")
    pages = PdfReader(paper["source_path"]).pages
    assert len(pages) == 3
    assert "SYNTHETIC TEACHING MATERIAL" in pages[0].extract_text()
    assert "invented values, NOT an experiment" in pages[1].extract_text()
    assert "No error bars" in pages[1].extract_text()
    assert Path(paper["source_path"]).is_relative_to(store.root)
    session = store.list("session", paper["id"])[0]
    assert not session["note_consent"] and not session["learning_consent"]
    assert store.setting("zotero") is None and store.setting("vault") is None
    assert store.list("note", paper["id"])[0]["content"].startswith("【示例原话】")


def test_demo_refuses_to_overwrite_an_existing_directory(tmp_path):
    marker = tmp_path / "my-paper.pdf"
    marker.write_text("personal")
    with pytest.raises(ValueError, match="不会覆盖"):
        prepare_demo(tmp_path)
    assert marker.read_text() == "personal"
    assert not (tmp_path / "notebook.sqlite3").exists()


def test_demo_cli_uses_its_own_port_and_rejects_invalid_ports():
    args = parser().parse_args(["--no-open"])
    assert args.port == 8766 and args.no_open
    with pytest.raises(ValueError, match="端口"):
        serve_demo(port=80, no_open=True)


def test_demo_server_cleanup_does_not_touch_default_library(tmp_path, monkeypatch):
    import uvicorn
    personal = tmp_path / "personal"
    monkeypatch.setenv("PRC_DATA_DIR", str(personal))
    seen = []
    def run(app, **kwargs):
        seen.append(app.state.store.root)
        assert kwargs["host"] == "127.0.0.1"
        assert kwargs["port"] == 8766
        assert len(app.state.store.list("paper")) == 1
    monkeypatch.setattr(uvicorn, "run", run)
    serve_demo(no_open=True)
    assert seen and not seen[0].exists()
    assert not personal.exists()


def test_lean_runtime_includes_local_reading_and_language_help():
    assert "不是讲解门禁" in RULES and "翻译保留限定词" in RULES
    assert len(bootstrap({"title": "T" * 500, "page_count": 12},
                         {"goal": "G" * 20000, "next_action": "N" * 20000,
                          "pending_question": "Q" * 20000})) <= 3000

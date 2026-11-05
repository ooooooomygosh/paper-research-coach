import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas
from test_coach import FakeRPC
from test_reading import start, turn

from paper_research_coach import locate
from paper_research_coach.coach import Coach
from paper_research_coach.server import create_app
from paper_research_coach.store import Store


@pytest.fixture
def paper_pdf(tmp_path):
    """Three pages: a claim, a sentence hyphenated across lines, and a page with no text."""
    path = tmp_path / "located.pdf"
    c = canvas.Canvas(str(path), pagesize=(600, 800))
    c.drawString(60, 720, "Introduction. Prior sensing policies observe on a fixed clock.")
    c.drawString(60, 700, "We show that event-triggered sensing improves decision utility by two units.")
    c.showPage()
    c.drawString(60, 720, "Both policies receive twenty observa-")
    c.drawString(60, 700, "tions per episode, so the budget is matched.")
    c.drawString(60, 680, "No error bars are reported.")
    c.showPage()
    c.rect(100, 100, 300, 300, fill=1)  # a figure with no text layer
    c.showPage()
    c.save()
    return path


@pytest.fixture
def located(tmp_path, paper_pdf):
    store = Store(tmp_path / "lib")
    return store, store.add_paper("Located paper", str(paper_pdf))


def test_normalize_keeps_a_map_back_to_the_source():
    text, where = locate.normalize("Curly “quotes” — fiﬁx\r\nnext")
    assert text == 'curly "quotes" - fifix next'
    assert where[text.index("fifix") + 2] == "Curly “quotes” — fiﬁx".index("ﬁ")


def test_match_tolerates_case_spacing_and_line_break_hyphens_but_not_other_words():
    page = "Both policies receive twenty observa-\r\ntions per episode."
    assert locate.match(page, "BOTH policies  receive twenty observations") == (0, page.index("tions") + 5)
    assert locate.match(page, "receive twenty observa- tions per") is not None
    assert locate.match(page, "receive thirty observations") is None
    assert locate.match(page, "Both") is None  # too short to point at


def test_quotes_on_a_page_come_back_as_pdf_rectangles(located):
    store, paper = located
    result = locate.page_quotes(store, paper["id"], 0, [
        "We show that event-triggered sensing improves decision utility",
        "a sentence the paper never says",
    ])
    assert result["has_text"] and result["missing"] == ["a sentence the paper never says"]
    (found,) = result["found"]
    (x0, y0, x1, y1), = found["rects"]
    # PDF user space: the second line sits at y=700 on a 800pt page.
    assert 55 < x0 < 65 and 695 < y0 < 702 and y1 < 712 and x1 > 300
    hyphenated = locate.page_quotes(store, paper["id"], 1, ["twenty observations per episode, so the budget is matched"])
    assert len(hyphenated["found"][0]["rects"]) == 2  # one band per line
    with pytest.raises(ValueError, match="页码"):
        locate.page_quotes(store, paper["id"], 9, ["x"])


def test_search_returns_pages_and_snippets(located):
    store, paper = located
    result = locate.search(store, paper["id"], "error bars")
    assert [h["page_index"] for h in result["hits"]] == [1]
    assert "No [error bars] are reported" in result["hits"][0]["snippet"]
    assert result["pages_without_text"] == 1 and result["untrusted_source"]
    assert locate.search(store, paper["id"], "observations")["hits"][0]["page_index"] == 1


def test_prc_show_marks_real_sentences_and_refuses_made_up_ones(located):
    store, paper = located
    start(store, paper)
    coach = Coach(store, FakeRPC)
    state = turn(coach, paper, "follow") | {"shows": 0}
    with pytest.raises(ValueError, match="逐字复制"):
        coach.tool_call(state, "prc_show", {"page_index": 0, "quotes": ["Event-triggered sensing is always better."]}, "s0")
    assert state["shows"] == 0 and not state["answer"]["actions"]
    reply = coach.tool_call(state, "prc_show", {"page_index": 0, "quotes": [
        "We show that event-triggered sensing improves decision utility by two units.",
        "Prior sensing policies observe on a fixed clock.",
    ], "note": "作者的主张"}, "s1")
    assert reply["shown"] and reply["marked"] == 2 and 0 in state["read_pages"]
    action = state["answer"]["actions"][-1]
    assert action["kind"] == "focus" and action["label"] == "第 1 页 · 作者的主张"
    assert [m["n"] for m in action["marks"]] == [1, 2] and action["anchor"]["status"] == "verified"
    assert action["anchor"]["page_index"] == 0 and action["anchor"]["quote"].startswith("We show")
    assert len(action["anchor"]["rects"]) == 2
    # A page without text: the reader is taken there, nothing is marked, the page is not "read".
    scan = coach.tool_call(state, "prc_show", {"page_index": 2, "quotes": ["the black square"]}, "s2")
    assert scan["needs_visual_reading"] and scan["marked"] == 0 and 2 not in state["read_pages"]
    coach.tool_call(state, "prc_show", {"page_index": 1, "quotes": ["No error bars are reported."]}, "s3")
    with pytest.raises(ValueError, match="3 处"):
        coach.tool_call(state, "prc_show", {"page_index": 1, "quotes": ["No error bars are reported."]}, "s4")


def test_prc_find_and_the_http_and_cli_paths(located, monkeypatch, capsys):
    store, paper = located
    coach = Coach(store, FakeRPC)
    state = turn(coach, paper, "detour")
    found = coach.tool_call(state, "prc_find", {"query": "fixed clock"}, "f1")
    assert found["hits"][0]["page_index"] == 0
    app = create_app(store, "token")
    client = TestClient(app, base_url="http://127.0.0.1")
    headers = {"Authorization": "Bearer token"}
    shown = client.post(f"/api/coach/show/{paper['id']}", json={"page_index": 1, "quotes": ["No error bars are reported."], "note": "缺什么"}, headers=headers)
    assert shown.status_code == 200, shown.text
    last = client.get(f"/api/coach/conversation/{paper['id']}", headers=headers).json()["messages"][-1]
    assert last["actions"][0]["kind"] == "focus" and last["actions"][0]["marks"][0]["n"] == 1
    bad = client.post(f"/api/coach/show/{paper['id']}", json={"page_index": 1, "quotes": ["invented words here"]}, headers=headers)
    assert bad.status_code == 400 and "逐字复制" in bad.json()["error"]
    assert client.get(f"/api/find/{paper['id']}?q=budget", headers=headers).json()["hits"][0]["page_index"] == 1
    from paper_research_coach import cli
    monkeypatch.setattr("sys.argv", ["prc", "--data-dir", str(store.root), "find", "--paper", paper["id"], "decision utility"])
    cli.main()
    assert '"page_index": 0' in capsys.readouterr().out

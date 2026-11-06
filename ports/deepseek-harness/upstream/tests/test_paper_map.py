import pytest
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

from paper_research_coach import paper_map
from paper_research_coach.store import Conflict

BODY = ("Helvetica", 10)
HEAD = ("Helvetica-Bold", 13)


def make(path, pages, bookmarks=None):
    """pages: a list of pages; a page is a list of (x, y, (font, size), text). bookmarks: {page: [(title, level)]}."""
    c = canvas.Canvas(str(path), pagesize=(600, 800))
    for number, lines in enumerate(pages):
        for x, y, (font, size), text in lines:
            c.setFont(font, size)
            c.drawString(x, y, text)
        for k, (title, level) in enumerate((bookmarks or {}).get(number, [])):
            key = f"p{number}-{k}"
            c.bookmarkPage(key)
            c.addOutlineEntry(title, key, level)
        c.showPage()
    c.save()
    return path


def running(text="Synthetic Sensing Paper  arXiv:2601.00001"):
    return (60, 780, ("Helvetica", 8), text)  # a header that repeats on every page


def prose(y, text="The policy observes when the estimated decision loss grows past a threshold."):
    return (60, y, BODY, text)


@pytest.fixture(autouse=True)
def fresh_cache():
    paper_map._cache.clear()


def three_pages(tmp_path, bookmarks=None):
    return make(
        tmp_path / "paper.pdf",
        [
            [running(), (60, 740, HEAD, "Abstract"), prose(715), prose(701), (60, 660, HEAD, "1 Introduction"), prose(635),
             # lines that look a little like headings or captions but are neither
             (60, 610, BODY, "Figure 1 shows the setting of this study in some detail."),
             (60, 590, BODY, "1. Question: Does the policy really need such a thing?"),
             (60, 570, BODY, "Method"),
             (60, 550, BODY, "2 Hz sampling is used for the baseline in all of the experiments."),
             ],
            [running(), (60, 740, HEAD, "2 Method"), prose(715), (60, 680, HEAD, "2.1 Trigger rule"), prose(655),
             (60, 500, BODY, "Figure 1: Overview of the sensing loop and where the budget"),
             (60, 488, BODY, "is spent in each episode."),
             (60, 400, BODY, "Table 1: Utility at equal observation budget (higher is better)"),
             (320, 388, BODY, "right column body text that must stay out of the caption"),
             (60, 376, BODY, "second line of the table caption"),
             ],
            [running(), (60, 740, HEAD, "3 Conclusion"), prose(715), (60, 660, HEAD, "References"), prose(635, "[1] A. Author. Event-triggered control. 2010.")],
        ],
        bookmarks,
    )


def test_headings_are_found_by_pattern_and_type_not_by_pattern_alone(tmp_path):
    m = paper_map.build(str(three_pages(tmp_path)))
    assert m["outline_source"] == "heading"
    got = [(e["title"], e["page_index"], e["depth"]) for e in m["outline"]]
    assert got == [
        ("Abstract", 0, 0), ("1 Introduction", 0, 0), ("2 Method", 1, 0), ("2.1 Trigger rule", 1, 1),
        ("3 Conclusion", 2, 0), ("References", 2, 0),
    ]
    titles = " ".join(e["title"] for e in m["outline"])
    for trap in ("Question", "Hz sampling", "arXiv", "Figure 1 shows"):
        assert trap not in titles
    assert "Method" not in [e["title"] for e in m["outline"]]  # a table cell, set like body text


def test_captions_are_found_joined_in_their_own_column_and_never_glued_to_another(tmp_path):
    m = paper_map.build(str(three_pages(tmp_path)))
    by_label = {f["label"]: f for f in m["figures"]}
    assert set(by_label) == {"Figure 1", "Table 1"}  # "Figure 1 shows ..." in the prose is a mention, not a caption
    assert by_label["Figure 1"]["page_index"] == 1
    assert by_label["Figure 1"]["caption"] == "Overview of the sensing loop and where the budget is spent in each episode."
    assert by_label["Table 1"]["kind"] == "table"
    assert by_label["Table 1"]["caption"] == "Utility at equal observation budget (higher is better)"
    assert "right column" not in by_label["Table 1"]["caption"]


def test_the_pdf_s_own_bookmarks_win_and_are_cleaned(tmp_path):
    marks = {0: [("Abstract", 0), ("1  Introduction", 0), ("1  Introduction", 0)], 1: [("2 Method", 0), ("2.1 Trigger rule", 1)]}
    m = paper_map.build(str(three_pages(tmp_path, marks)))
    assert m["outline_source"] == "bookmark"
    assert [(e["title"], e["page_index"], e["depth"]) for e in m["outline"]] == [
        ("Abstract", 0, 0), ("1 Introduction", 0, 0), ("2 Method", 1, 0), ("2.1 Trigger rule", 1, 1),
    ]  # a repeated bookmark is dropped and spacing is normalised


def test_chinese_numbered_headings_are_recognised(tmp_path):
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    zh, small = ("STSong-Light", 14), ("STSong-Light", 10)
    body = "本文研究在固定预算下传感器应当何时进行观测，并比较两种策略的差别。"
    path = make(
        tmp_path / "zh.pdf",
        [
            [(60, 740, zh, "摘要"), (60, 715, small, body), (60, 680, zh, "1 引言"), (60, 655, small, body)],
            [(60, 740, zh, "2 方法"), (60, 715, small, body), (60, 680, small, "图 1：这是一行正文，不是标题")],
        ],
    )
    m = paper_map.build(str(path))
    assert [e["title"] for e in m["outline"]] == ["摘要", "1 引言", "2 方法"]


def test_a_pdf_without_text_gives_an_empty_map_and_does_not_fail(tmp_path):
    c = canvas.Canvas(str(tmp_path / "scan.pdf"), pagesize=(600, 800))
    c.rect(100, 100, 300, 300, fill=1)  # a figure, no text layer
    c.showPage()
    c.save()
    m = paper_map.build(str(tmp_path / "scan.pdf"))
    assert m["outline_source"] == "none" and m["outline"] == [] and m["figures"] == []
    assert m["page_count"] == 1


def test_get_builds_once_per_version_and_refuses_a_changed_pdf(store, tmp_path):
    path = three_pages(tmp_path)
    paper = store.add_paper("Synthetic", str(path))
    first = paper_map.get(store, paper["id"])
    assert first["untrusted_source"] is True and first["source_version"] == paper["source_version"]
    assert first["note"] and first["outline"]
    paper_map._cache[paper["source_version"]]["outline"] = [{"title": "from cache", "page_index": 0, "depth": 0}]
    assert paper_map.get(store, paper["id"])["outline"][0]["title"] == "from cache"  # not rebuilt
    make(path, [[running(), prose(700)]])  # the file on disk is replaced behind the library's back
    with pytest.raises(Conflict):
        paper_map.get(store, paper["id"])


def test_a_paper_without_a_local_pdf_has_an_empty_map(store):
    paper = store.add_paper("Metadata only")
    m = paper_map.get(store, paper["id"])
    assert m["outline"] == [] and m["figures"] == [] and m["outline_source"] == "none"


def test_the_section_line_says_what_carries_over_and_what_starts_here():
    m = {"outline": [
        {"title": "2 Method", "page_index": 1, "depth": 0},
        {"title": "2.1 Trigger rule", "page_index": 1, "depth": 1},
        {"title": "3 Experiments", "page_index": 3, "depth": 0},
    ]}
    assert paper_map.section_note(m, 0) == ""
    assert paper_map.section_note(m, 1) == "本页开始「2 Method」「2.1 Trigger rule」"
    assert paper_map.section_note(m, 2) == "承接「2.1 Trigger rule」"
    assert paper_map.section_note(m, 3) == "承接「2.1 Trigger rule」；本页开始「3 Experiments」"
    assert paper_map.section_note({"outline": []}, 2) == ""


def test_the_coach_is_told_where_the_reader_is_and_can_ask_for_the_whole_map(store, tmp_path):
    import asyncio

    from fastapi.testclient import TestClient
    from test_coach import FakeRPC, drained
    from test_reading import turn

    from paper_research_coach.coach import Coach, Send
    from paper_research_coach.server import create_app

    paper = store.add_paper("Synthetic", str(three_pages(tmp_path)))

    async def run():
        coach = Coach(store, FakeRPC)
        await coach.send(paper["id"], Send(operation_id="a", content="what is this section about?", page_index=2))
        await drained(coach)
        sent = next(params for method, params in coach.rpc.calls if method == "turn/start")
        lines = [item["text"] for item in sent["input"] if item["type"] == "text"]
        place = [line for line in lines if line.startswith("本页位置")]
        assert place and "承接「2.1 Trigger rule」" in place[0] and "本页开始「3 Conclusion」「References」" in place[0]
        await coach.close()

    asyncio.run(run())

    coach = Coach(store, FakeRPC)
    result = coach.tool_call(turn(coach, paper, "detour"), "prc_map", {}, "m1")
    assert result["outline_source"] == "heading" and result["untrusted_source"] is True
    assert {f["label"] for f in result["figures"]} == {"Figure 1", "Table 1"}
    assert "prc_map" in [t["name"] for t in __import__("paper_research_coach.coach", fromlist=["TOOLS"]).TOOLS]

    client = TestClient(create_app(store, "token"), base_url="http://127.0.0.1")
    over_http = client.get(f"/api/map/{paper['id']}", headers={"Authorization": "Bearer token"})
    assert over_http.status_code == 200 and over_http.json()["outline"][0]["title"] == "Abstract"
    assert client.get(f"/api/map/{paper['id']}").status_code == 401


def test_a_map_that_cannot_be_built_never_stops_a_turn(store, tmp_path, monkeypatch):
    import asyncio

    from test_coach import FakeRPC, drained

    from paper_research_coach.coach import Coach, Send

    paper = store.add_paper("Synthetic", str(three_pages(tmp_path)))
    monkeypatch.setattr(paper_map, "get", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("pdfium said no")))

    async def run():
        coach = Coach(store, FakeRPC)
        sent = await coach.send(paper["id"], Send(operation_id="a", content="hello", page_index=0))
        await drained(coach)
        assert coach.messages(sent["conversation_id"])[-1]["status"] == "completed"
        turn_start = next(params for method, params in coach.rpc.calls if method == "turn/start")
        assert not any(i["text"].startswith("本页位置") for i in turn_start["input"] if i["type"] == "text")
        await coach.close()

    asyncio.run(run())


def test_the_cli_prints_the_map_without_a_running_workbench(store, tmp_path, monkeypatch, capsys):
    from paper_research_coach import cli

    paper = store.add_paper("Synthetic", str(three_pages(tmp_path)))
    monkeypatch.setattr("sys.argv", ["prc", "--data-dir", str(store.root), "map", "--paper", paper["id"]])
    cli.main()
    out = capsys.readouterr().out
    assert '"outline_source": "heading"' in out and "2.1 Trigger rule" in out and "Table 1" in out

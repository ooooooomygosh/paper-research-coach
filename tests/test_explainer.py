import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_coach import FakeRPC, drained
from test_reading import start, turn

from paper_research_coach import explainer
from paper_research_coach.coach import Coach, Send
from paper_research_coach.explainer import DraftError, parse_draft
from paper_research_coach.server import create_app

FIXTURES = Path(__file__).parent / "fixtures" / "explainers"
DRAFT = """---
title: Why the comparison is not fair
---
Short answer: the two policies use different budgets.

## Budget
```flow LR
(Fixed) -> Observe 20 times: each episode
(Event) -> Observe 40 times: each episode
Observe 20 times -> *Utility 61
Observe 40 times -> *Utility 70
```
| Policy | Budget | Fair |
|---|---|---|
| Fixed | 20 | ok |
| Event | 40 | no twice as many |

## Next check
```ask
Which check first?
* Equal budget | most direct
- Error bars | needs repeated runs
```
"""


def test_fixtures_all_parse_and_cover_every_component():
    seen = set()
    for path in sorted(FIXTURES.glob("*.md")):
        draft = parse_draft(path.read_text(encoding="utf-8"))
        assert draft.doc["title"]
        for b in draft.doc["lead"] + [b for p in draft.doc["panels"] for b in p["blocks"]]:
            seen.add(b["type"])
    assert set(explainer.COMPONENTS) <= seen and "md" in seen


def test_parser_returns_typed_blocks_and_flow_semantics():
    doc = parse_draft(DRAFT).doc
    assert doc["title"] == "Why the comparison is not fair" and doc["lang"] == "en"
    flow = doc["panels"][0]["blocks"][0]
    assert flow["type"] == "flow" and flow["dir"] == "LR"
    ids = [n["id"] for n in flow["nodes"]]
    assert ids == ["Fixed", "Observe 20 times", "Event", "Observe 40 times", "Utility 61", "Utility 70"]
    assert {n["id"]: n["shape"] for n in flow["nodes"]}["Fixed"] == "round"
    assert [n["hi"] for n in flow["nodes"] if n["id"] == "Utility 61"] == [True]
    assert flow["edges"][0] == {"from": "Fixed", "to": "Observe 20 times", "dashed": False, "label": "each episode"}
    ask = doc["panels"][1]["blocks"][0]
    assert ask["type"] == "ask" and ask["options"][0]["suggested"] and not ask["multi"]


@pytest.mark.parametrize(
    "bad,where",
    [
        ("## x\n```flow\nA -> \n```", "flow"),
        ("## x\n```ask\nQ?\n* a\n* b\n```", "ask"),
        ("## x\n```ask\nQ?\n* only one\n```", "ask"),
        ("## x\n```sequence\nA -> A: hi\n```", "sequence"),
        ("## x\n```timeline\n2020\n```", "timeline"),
        ("## x\n```kv\nno colon here\n```", "kv"),
        ("## x\n```tree\n\n```", "tree"),
    ],
)
def test_errors_name_the_line_the_component_and_a_correct_example(bad, where):
    with pytest.raises(DraftError) as caught:
        parse_draft(bad)
    message = str(caught.value)
    assert f"[{where}]" in message and "L" in message.splitlines()[0] and "Correct example:" in message


def test_limits_and_unclosed_fences_are_refused():
    with pytest.raises(DraftError, match="never closed"):
        parse_draft("## x\n```flow\nA -> B")
    with pytest.raises(DraftError, match="max"):
        parse_draft("x" * (explainer.MAX_DRAFT + 1))
    with pytest.raises(DraftError, match="too many panels"):
        parse_draft("\n".join(f"## p{i}\ntext" for i in range(explainer.MAX_PANELS + 1)))
    with pytest.raises(DraftError, match="empty"):
        parse_draft("  \n ")


def test_html_and_scripts_in_a_draft_stay_inert_text():
    doc = parse_draft("## x\n<script>alert(1)</script> and <img src=x onerror=alert(1)>").doc
    block = doc["panels"][0]["blocks"][0]
    assert block["type"] == "md" and "<script>" in block["text"]  # kept as text; the browser never injects it


def test_plain_writing_check_english_and_chinese():
    long_en = "This sentence keeps going and going without any real reason to stop because the writer never decided where the thought ends and so the reader must wait a long time."
    warnings = parse_draft(f"## x\n{long_en}\nWe utilize a method that was built by them.").warnings
    rules = {w["rule"] for w in warnings}
    assert {"sentence-length", "word", "passive"} <= rules
    zh = parse_draft("## x\n进行优化之前，先看预算。这个结果至关重要。\n- 点击 登陆 按钮。").warnings
    messages = " ".join(w["message"] for w in zh)
    assert "进行" in messages and "至关重要" in messages and "登陆" in messages
    clean = parse_draft("## x\nThe two policies use different budgets.\n1. Compare the budgets.").warnings
    assert clean == []


def test_style_check_skips_code_math_and_counter_examples():
    text = "## x\n```python\nutilize = 1  # prior to this we commence\n```\n$$a_i \\ge b_i$$\n~~We utilize it~~\n| a | b |\n|---|---|\n| no | We utilize it |"
    assert parse_draft(text).warnings == []


def test_coach_tool_saves_a_branch_and_marks_the_message(store, paper):
    start(store, paper)
    coach = Coach(store, FakeRPC)
    state = turn(coach, paper, "detour")
    state.update(message={"content": "What is the budget?", "anchor": None}, explains=0, branch_id="")
    result = coach.tool_call(state, "prc_explain", {"draft": DRAFT}, "call-1")
    assert result["opened"] and "style_warnings" not in result
    record = coach.explainer(result["id"], paper["id"])
    assert record["branch_id"] == record["id"] and record["seq"] == 1
    assert record["return_point"]["step"] == "orient" and record["question"] == "What is the budget?"
    action = state["answer"]["actions"][-1]
    assert action["kind"] == "explainer" and action["id"] == result["id"]
    # An HTTP retry of the same tool call is the same page, not a second one.
    again = coach.tool_call(state | {"explains": 0}, "prc_explain", {"draft": DRAFT}, "call-1")
    assert again["id"] == result["id"] and len(coach.explainer_list(paper["id"])) == 1
    # A follow-up in the branch becomes page 2; replacing keeps the id and the place.
    follow = turn(coach, paper, "detour")
    follow.update(message={"content": "And error bars?", "anchor": None}, explains=0, branch_id=record["branch_id"])
    second = coach.tool_call(follow, "prc_explain", {"draft": DRAFT}, "call-2")
    assert coach.explainer(second["id"])["seq"] == 2 and coach.explainer(second["id"])["branch_id"] == record["id"]
    follow["explains"] = 0
    replaced = coach.tool_call(follow, "prc_explain", {"draft": DRAFT, "replace_id": second["id"]}, "call-3")
    assert replaced["id"] == second["id"] and len(coach.explainer_list(paper["id"])) == 2


def test_coach_tool_returns_fixable_errors_and_style_hints(store, paper):
    start(store, paper)
    coach = Coach(store, FakeRPC)
    state = turn(coach, paper, "detour")
    state.update(message={"content": "q", "anchor": None}, explains=0, branch_id="")
    with pytest.raises(ValueError, match=r"\[flow\]"):
        coach.tool_call(state, "prc_explain", {"draft": "## x\n```flow\nA ->\n```"}, "bad")
    noisy = "## x\nWe utilize the method. It is utilized in order to commence the work."
    result = coach.tool_call(state, "prc_explain", {"draft": noisy}, "noisy")
    assert result["style_warnings"] and "replace_id=" + result["id"] in result["next"]


def test_the_mainline_gets_one_inline_figure_but_never_a_branch_and_calls_are_capped(store, paper):
    start(store, paper)
    coach = Coach(store, FakeRPC)
    follow = turn(coach, paper, "follow")
    follow.update(message={"content": "", "anchor": None}, explains=0, branch_id="")
    with pytest.raises(ValueError, match="不开插话面板"):
        coach.tool_call(follow, "prc_explain", {"draft": DRAFT, "place": "panel"}, "c")
    figure = coach.tool_call(follow, "prc_explain", {"draft": DRAFT}, "c1")
    assert figure["place"] == "chat"
    action = follow["answer"]["actions"][-1]
    assert action["mainline"] and action["label"].startswith("图解 · ")
    record = coach.explainer(figure["id"], paper["id"])
    assert record["origin"] == "mainline" and record["question"] == ""
    # A rewrite of the same figure is fine; a second figure is not.
    coach.tool_call(follow, "prc_explain", {"draft": DRAFT, "replace_id": figure["id"]}, "c2")
    with pytest.raises(ValueError, match="一张图解"):
        coach.tool_call(follow, "prc_explain", {"draft": DRAFT}, "c3")
    # The mainline figure does not count as a branch panel, and a detour cannot put one in the chat.
    assert follow["explains"] == 0
    question = turn(coach, paper, "detour")
    question.update(message={"content": "q", "anchor": None}, explains=0, branch_id="")
    with pytest.raises(ValueError, match="place=panel"):
        coach.tool_call(question, "prc_explain", {"draft": DRAFT, "place": "chat"}, "c4")
    detour = turn(coach, paper, "detour")
    detour.update(message={"content": "q", "anchor": None}, explains=3, branch_id="")
    with pytest.raises(ValueError, match="3 次"):
        coach.tool_call(detour, "prc_explain", {"draft": DRAFT}, "c2")


def test_unknown_branch_is_refused_and_pages_stay_in_their_paper(store, paper, pdf):
    start(store, paper)
    coach = Coach(store, FakeRPC)
    with pytest.raises(ValueError, match="分支"):
        coach.branch_title(paper["id"], "no-such-branch")
    from reportlab.pdfgen import canvas

    second = pdf.parent / "second.pdf"
    c = canvas.Canvas(str(second), pagesize=(600, 800))
    c.drawString(60, 720, "A different synthetic paper.")
    c.showPage()
    c.save()
    other = store.add_paper("Other", str(second))
    assert other["id"] != paper["id"]
    state = turn(coach, paper, "detour")
    state.update(message={"content": "q", "anchor": None}, explains=0, branch_id="")
    page = coach.tool_call(state, "prc_explain", {"draft": DRAFT}, "p")
    with pytest.raises(KeyError):
        coach.explainer(page["id"], other["id"])


def test_follow_up_turn_names_the_branch_and_stays_within_the_prefix_limit(store, paper):
    coach = Coach(store, FakeRPC)
    start(store, paper)
    page = coach.explain_external(paper["id"], DRAFT.replace("Why the comparison is not fair", "T" * 80))

    async def run():
        sent = await coach.send(paper["id"], Send(operation_id="follow-up", content="And error bars?", branch_id=page["id"]))
        await drained(coach)
        turn_call = [p for m, p in coach.rpc.calls if m == "turn/start"][-1]
        assert "追问" in turn_call["input"][0]["text"] and len(turn_call["input"][0]["text"]) <= 300
        assert sent["message_id"]
        with pytest.raises(ValueError, match="分支"):
            await coach.send(paper["id"], Send(operation_id="bad-branch", content="x", branch_id="missing"))
        await coach.close()

    asyncio.run(run())


def test_http_api_cli_creation_adds_a_pointer_message(store, paper):
    app = create_app(store, "token")
    client = TestClient(app, base_url="http://127.0.0.1")
    headers = {"Authorization": "Bearer token"}
    created = client.post(f"/api/coach/explain/{paper['id']}", json={"draft": DRAFT, "question": "q"}, headers=headers)
    assert created.status_code == 200, created.text
    record = created.json()
    snapshot = client.get(f"/api/coach/conversation/{paper['id']}", headers=headers).json()
    last = snapshot["messages"][-1]
    assert last["actions"][0]["kind"] == "explainer" and last["actions"][0]["id"] == record["id"]
    assert client.get(f"/api/coach/explainer/{record['id']}", headers=headers).json()["doc"]["title"]
    listing = client.get(f"/api/coach/explainers/{paper['id']}", headers=headers).json()["data"]
    assert [x["id"] for x in listing] == [record["id"]]
    bad = client.post(f"/api/coach/explain/{paper['id']}", json={"draft": "## x\n```flow\nA ->\n```"}, headers=headers)
    assert bad.status_code == 400 and "Correct example" in bad.json()["error"]
    missing = client.get("/api/coach/explainer/nope", headers=headers)
    assert missing.status_code == 404


def test_cli_check_reports_warnings_without_a_workbench(tmp_path, capsys, monkeypatch):
    from paper_research_coach.cli import main

    draft = tmp_path / "d.md"
    draft.write_text("## x\nWe utilize it.", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["prc", "--data-dir", str(tmp_path / "d"), "explain", "--check", "--file", str(draft)])
    main()
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] and out["style_warnings"]


def test_replacing_a_page_updates_the_revision_the_browser_watches(store, paper):
    coach = Coach(store, FakeRPC)
    first = coach.explain_external(paper["id"], DRAFT)
    message = coach.messages(first["conversation_id"])[-1]
    assert message["actions"][0]["rev"] == first["updated_at"]
    second = coach.explain_external(paper["id"], DRAFT.replace("Short answer", "Short reply"), replace_id=first["id"])
    assert second["id"] == first["id"] and second["updated_at"] >= first["updated_at"]
    message = coach.messages(first["conversation_id"])[-1]
    assert message["actions"][0]["rev"] == second["updated_at"]
    assert len(coach.explainer_list(paper["id"])) == 1


def test_parsed_fixtures_are_current():
    """The browser tests render the committed *.doc.json; regenerate with scripts/build_explainer_fixtures.py."""
    for path in sorted(FIXTURES.glob("*.md")):
        committed = json.loads(path.with_suffix(".doc.json").read_text(encoding="utf-8"))
        assert committed == parse_draft(path.read_text(encoding="utf-8")).doc, f"stale: run scripts/build_explainer_fixtures.py ({path.name})"


def test_side_quest_state_is_set_by_the_reader_and_kept_verbatim(store, paper):
    app = create_app(store, "token")
    client = TestClient(app, base_url="http://127.0.0.1")
    headers = {"Authorization": "Bearer token"}
    first = client.post(f"/api/coach/explain/{paper['id']}", json={"draft": DRAFT, "question": "q"}, headers=headers).json()
    follow = client.post(f"/api/coach/explain/{paper['id']}", json={"draft": DRAFT, "branch_id": first["id"]}, headers=headers).json()
    mine = "  预算不同，所以 61 和 70 不能直接比 —— 我自己的话  "
    done = client.post(f"/api/coach/branch/{first['id']}/quest", json={"status": "done", "takeaway": mine}, headers=headers)
    assert done.status_code == 200, done.text
    assert done.json()["quest"]["takeaway"] == mine.strip() and done.json()["quest"]["closed_at"]
    listing = {x["id"]: x for x in client.get(f"/api/coach/explainers/{paper['id']}", headers=headers).json()["data"]}
    assert listing[first["id"]]["quest"]["status"] == "done" and listing[follow["id"]].get("quest") is None
    assert listing[first["id"]]["gist"] == "the two policies use different budgets."
    # Only the first page holds the state, and only the three statuses exist.
    assert client.post(f"/api/coach/branch/{follow['id']}/quest", json={"status": "done"}, headers=headers).status_code == 400
    assert client.post(f"/api/coach/branch/{first['id']}/quest", json={"status": "mastered"}, headers=headers).status_code == 400
    # Parking keeps the earlier takeaway; a rewrite of the page keeps the quest.
    parked = client.post(f"/api/coach/branch/{first['id']}/quest", json={"status": "parked"}, headers=headers).json()
    assert parked["quest"]["takeaway"] == mine.strip()
    coach = Coach(store, FakeRPC)
    coach.explain_external(paper["id"], DRAFT.replace("Short answer", "Short reply"), replace_id=first["id"])
    assert coach.explainer(first["id"])["quest"]["status"] == "parked"


def test_the_model_has_no_tool_to_close_a_side_quest():
    from paper_research_coach import coach as module

    names = [t["name"] for t in module.TOOLS]
    assert names and not [n for n in names if "quest" in n]

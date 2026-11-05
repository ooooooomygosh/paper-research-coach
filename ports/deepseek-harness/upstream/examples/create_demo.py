"""Create original synthetic teaching material; no real research result or personal data."""

from pathlib import Path
import sys
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from paper_research_coach.store import Store

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".prc/demo").resolve()
root.mkdir(parents=True, exist_ok=True)
path = root / "synthetic-paper.pdf"
c = canvas.Canvas(str(path), pagesize=(612, 792))


def heading(number, title, subtitle):
    c.setFillColor(HexColor("#527047"))
    c.setFont("Helvetica", 9)
    c.drawString(54, 746, "PAPER RESEARCH COACH  /  SYNTHETIC TEACHING MATERIAL")
    c.setFillColor(HexColor("#253b2b"))
    c.setFont("Times-Bold", 24)
    c.drawString(54, 695, title)
    c.setFont("Helvetica", 11)
    c.setFillColor(HexColor("#728166"))
    c.drawString(54, 670, subtitle)
    c.setStrokeColor(HexColor("#dce3d5"))
    c.line(54, 650, 558, 650)
    c.setFont("Helvetica", 9)
    c.drawString(
        54, 32, "Fictional study for testing reading workflows. No empirical claim."
    )
    c.drawRightString(558, 32, str(number))


def lines(y, strings):
    c.setFont("Times-Roman", 12)
    c.setFillColor(HexColor("#334130"))
    for s in strings:
        c.drawString(54, y, s)
        y -= 20


heading(1, "When should a sensor observe?", "A budget-matched thought experiment")
lines(
    620,
    [
        "1. The question",
        "An agent can purchase a fresh observation before making a decision.",
        "Observations improve information, but consume time and energy.",
        "Does observing on events help because of timing, or simply because",
        "the policy obtains more information than its fixed-rate baseline?",
    ],
)
lines(
    482,
    [
        "2. A provisional mechanism",
        "The proposed policy observes when the estimated decision loss grows.",
        "Its claimed advantage is to allocate a fixed observation budget to",
        "moments when missing information would change the action.",
    ],
)
c.setFillColor(HexColor("#eef3e7"))
c.roundRect(54, 306, 504, 72, 7, fill=1, stroke=0)
c.setFont("Helvetica-Bold", 11)
c.setFillColor(HexColor("#4b6640"))
c.drawString(72, 350, "Key distinction")
c.setFont("Times-Roman", 12)
c.drawString(
    72,
    328,
    "Better timing is a different explanation from a larger information budget.",
)
lines(
    270,
    [
        "3. What would distinguish these explanations?",
        "Compare methods with the same total number of observations.",
        "Measure downstream decision utility and observation cost together.",
        "The next page contains invented numbers for discussion, not evidence.",
    ],
)
c.showPage()
heading(
    2, "A discriminating comparison", "Figure 1 / invented values, not an experiment"
)
lines(
    620,
    [
        "Predict first: if the apparent gain comes only from extra observations,",
        "what should happen when both methods receive the same budget?",
    ],
)
labels = ["Fixed schedule", "Event trigger", "Information oracle"]
vals = [61, 63, 66]
for i, (label, value) in enumerate(zip(labels, vals)):
    y = 500 - i * 70
    c.setFont("Helvetica", 11)
    c.setFillColor(HexColor("#43583a"))
    c.drawString(54, y + 7, label)
    c.setFillColor(HexColor(["#c6d3b8", "#859f6e", "#516e45"][i]))
    c.rect(190, y, (value - 50) * 19, 25, fill=1, stroke=0)
    c.setFont("Helvetica", 11)
    c.setFillColor(HexColor("#43583a"))
    c.drawString(200 + (value - 50) * 19, y + 7, str(value))
lines(
    260,
    [
        "Figure 1. Utility at a shared budget of 20 observations per episode.",
        "Values 61, 63, and 66 are constructed examples. Error bars are absent.",
        "The comparison does not establish a reliable advantage.",
        "What variability and failure conditions would you need to inspect?",
    ],
)
c.showPage()
heading(
    3, "From a claim to a test", "A small research question, with a stopping condition"
)
lines(
    620,
    [
        "Observation: the advantage seems small at a matched budget.",
        "Hypothesis: timing matters only near action-changing events.",
        "Alternative: average gains reflect favorable trajectory selection.",
        "Simple baseline: a threshold rule with the same observation budget.",
        "Minimal test: compare slow changes and abrupt changes separately.",
        "Falsification: no consistent advantage in either condition.",
        "Decision: reconsider the target if even the oracle has little headroom.",
    ],
)
c.showPage()
c.save()
s = Store(root)
p = s.add_paper(
    "示例 · 何时值得获取一次新观测？",
    str(path),
    authors="Paper Research Coach · 合成教学材料",
    year="2026",
    goal="区分机制收益与额外信息带来的收益",
    status="reading",
)
session = s.list("session", p["id"])[0]
s.put(
    "session",
    session
    | {
        "stage": "evidence",
        "note_consent": True,
        "next_action": "先看第 2 页的图 1，比较相同观测预算下的三个结果。",
        "pending_question": "如果优势只是来自更多观测，预算匹配后结果应该怎样变化？",
        "support": {"evidence": "guided"},
        "cursor": {
            "paper_id": p["id"],
            "source_version": p["source_version"],
            "page_index": 1,
            "page_label": "2",
            "status": "verified",
        },
    },
    session["revision"],
)
if not s.list("note", p["id"]):
    s.put(
        "note",
        {
            "paper_id": p["id"],
            "content": "【示例原话】我怀疑增益只是来自额外的信息。应该先把观测预算对齐再比较。",
            "anchor": {
                "paper_id": p["id"],
                "source_version": p["source_version"],
                "page_index": 0,
                "page_label": "1",
                "quote": "Better timing is a different explanation from a larger information budget.",
                "rects": [[72, 325, 522, 342]],
                "status": "verified",
            },
        },
    )
    s.put(
        "review",
        {
            "paper_id": p["id"],
            "prompt": "不看笔记，解释为什么必须匹配观测预算，再评价触发机制。",
        },
    )
print(p["id"])

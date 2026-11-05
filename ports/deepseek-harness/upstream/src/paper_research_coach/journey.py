"""The journey of one reading: the mainline chapters, the side quests, and what the reader wrote.

Everything here is copied from records that exist (reading flow, conversation, explainer pages,
notes, ideas, reviews). Nothing is summarised by a model, and nothing is scored. The reader's
answers and takeaways are kept as written; the coach's reply is cut to its first sentence.
"""

import json
import re
import sqlite3
from datetime import datetime

from . import explainer as explainers
from . import reading

SENTENCE_END = re.compile(r"(?<=[。！？!?])|(?<=\.)\s")
PRESET = re.compile(r"^\s*>?\s*\**预设[^\n]*\n+")


def first_sentence(text: str, limit: int = 160) -> str:
    text = PRESET.sub("", text or "")
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_`#>]+", "", text)
    text = " ".join(text.split())
    head = next((p.strip() for p in SENTENCE_END.split(text) if p and p.strip()), "")
    return head if len(head) <= limit else head[: limit - 1] + "…"


def _time(value: str):
    try:
        return datetime.fromisoformat((value or "").replace("Z", "+00:00"))
    except ValueError:
        return None


def _rows(store, sql, args):
    """Read the coach's tables without the coach: a library that never used it has none."""
    try:
        with store.connect() as db:
            return [json.loads(r[0]) for r in db.execute(sql, args)]
    except sqlite3.OperationalError:
        return []


def _conversation(store, paper_id):
    try:
        with store.connect() as db:
            row = db.execute("SELECT conversation_id FROM coach_paper_bindings WHERE paper_id=?", (paper_id,)).fetchone()
    except sqlite3.OperationalError:
        return ""
    return row[0] if row else ""


def build(store, paper_id: str) -> dict:
    paper = store.get("paper", paper_id)
    session = store.list("session", paper_id)[0]
    flow = reading.snapshot(session, paper)
    done = {c["step"]: c for c in flow["completed"]}
    chapters = []
    for n, (key, label, goal) in enumerate(reading.STEPS, 1):
        c = done.get(key)
        state = "done" if c else "current" if flow["status"] == "active" and flow["current"] == key else "todo"
        chapters.append({
            "id": key, "n": n, "label": label, "goal": goal, "check": reading.CHECKS[key], "status": state,
            "takeaway": (c or {}).get("takeaway", ""), "evidence": (c or {}).get("evidence", ""),
            "page_index": (c or {}).get("page_index"), "finished_at": (c or {}).get("finished_at", ""),
            "task": flow["pending_question"] if state == "current" else "",
            "marks": [], "exchanges": [], "questions": [], "side_quests": [], "notes": [], "ideas": [], "reviews": [],
        })
    by_key = {c["id"]: c for c in chapters}
    other = {"exchanges": [], "questions": [], "side_quests": [], "notes": [], "ideas": [], "reviews": []}

    def home(step):
        return by_key.get(step) if step and flow["status"] != "not_started" else None

    # The conversation: answers to tasks (verbatim) with the coach's first sentence, detour questions, marks.
    messages = _rows(store, "SELECT data FROM coach_messages WHERE conversation_id=? ORDER BY position", (_conversation(store, paper_id),))
    explained = {m.get("id") for m in messages if any(a.get("kind") == "explainer" and not a.get("mainline") for a in m.get("actions") or [])}
    task = ("", "")  # (chapter, question): a task only belongs to answers in its own chapter
    for i, m in enumerate(messages):
        if m.get("role") == "assistant":
            if m.get("task"):
                task = (m.get("step", ""), m["task"].get("question", ""))
            target = home(m.get("step"))
            for a in m.get("actions") or []:
                if a.get("kind") != "focus" or not target or m.get("intent") not in ("follow", "answer"):
                    continue
                page = (a.get("anchor") or {}).get("page_index")
                for mark in a.get("marks") or []:
                    quote = mark.get("quote", "")
                    if quote and all(x["quote"] != quote for x in target["marks"]):
                        target["marks"].append({"quote": quote, "page_index": page, "message_id": m["id"]})
            continue
        content = (m.get("content") or "").strip()
        if m.get("role") != "user" or not content:
            continue
        reply = next((r for r in messages[i + 1:] if r.get("role") == "assistant"), None)
        if m.get("branch_id") or (reply and reply.get("id") in explained):
            continue  # a side quest: it appears below with its page
        item = {"text": content[:2000], "message_id": m["id"], "reply": first_sentence((reply or {}).get("content", "")),
                "reply_id": (reply or {}).get("id", ""), "page_index": (m.get("anchor") or {}).get("page_index")}
        target = home(m.get("step"))
        if m.get("intent") == "answer":
            (target or other)["exchanges"].append({**item, "task": task[1] if task[0] == m.get("step") else ""})
        elif m.get("intent") == "detour":
            (target or other)["questions"].append(item)

    # Side quests: one per branch, filed under the chapter where the mainline paused.
    records = _rows(store, "SELECT data FROM coach_explainers WHERE paper_id=? ORDER BY rowid", (paper_id,))
    pages = {}
    for s in records:
        if s.get("origin") != "mainline":
            pages[s["branch_id"]] = pages.get(s["branch_id"], 0) + 1
    for s in records:
        if s.get("origin") == "mainline" or s["id"] != s["branch_id"]:
            continue
        quest = s.get("quest") or {}
        point = s.get("return_point") or {}
        item = {
            "branch_id": s["id"], "title": s["title"], "question": s.get("question", ""), "gist": explainers.gist(s.get("doc") or {}),
            "status": quest.get("status", "open"), "takeaway": quest.get("takeaway", ""), "pages": pages.get(s["id"], 1),
            "page_index": (s.get("anchor") or {}).get("page_index"), "created_at": s.get("created_at", ""),
        }
        target = by_key.get(point.get("step")) if point.get("status") == "active" else None
        (target or other)["side_quests"].append(item)

    # Notes, ideas and review questions go under the chapter that was current when they were written.
    bounds = []
    start = _time(flow["started_at"])
    previous = start
    for c in chapters:
        end = _time(c["finished_at"]) if c["status"] == "done" else None
        if c["status"] in ("done", "current") and previous:
            bounds.append((c, previous, end))
        previous = end or previous

    def chapter_at(created):
        t = _time(created)
        if not t or not start or t < start:
            return None
        for c, lo, hi in bounds:
            if lo <= t and (hi is None or t <= hi):
                return c
        return None

    for n in store.list("note", paper_id):
        item = {"id": n["id"], "text": n["content"][:600], "author": n.get("author", "user"),
                "provenance": n.get("provenance", "USER"), "page_index": (n.get("anchor") or {}).get("page_index"),
                "quote": ((n.get("anchor") or {}).get("quote") or "")[:300]}
        (chapter_at(n.get("created_at", "")) or other)["notes"].append(item)
    for idea in store.list("idea", paper_id):
        item = {"id": idea["id"], "title": idea["title"], "hypothesis": idea.get("hypothesis", ""), "status": idea.get("status", "seed")}
        (chapter_at(idea.get("created_at", "")) or other)["ideas"].append(item)
    for review in store.list("review", paper_id):
        item = {"id": review["id"], "prompt": review["prompt"], "page_index": (review.get("anchor") or {}).get("page_index")}
        (chapter_at(review.get("created_at", "")) or other)["reviews"].append(item)

    side = [q for c in chapters for q in c["side_quests"]] + other["side_quests"]
    return {
        "paper": {k: paper.get(k, "") for k in ("id", "title", "authors", "year", "goal")},
        "status": flow["status"],
        "started_at": flow["started_at"],
        # The root judgement is the reader's chapter-6 takeaway, if there is one.
        "verdict": by_key["synthesis"]["takeaway"],
        "chapters": chapters,
        "other": other,
        "counts": {
            "chapters_done": len(done), "chapters": len(chapters), "side_quests": len(side),
            "side_quests_done": sum(q["status"] == "done" for q in side),
            "answers": sum(len(c["exchanges"]) for c in chapters) + len(other["exchanges"]),
        },
    }


def markdown(journey: dict) -> str:
    """The journey as Markdown, for the paper card export."""
    lines = ["## 主线与支线", ""]
    if journey["verdict"]:
        lines += [f"**核心判断（第 6 章收获）**：{journey['verdict']}", ""]

    def quests(items, indent=""):
        out = []
        for q in items:
            mark = {"done": "✓", "parked": "‖"}.get(q["status"], "…")
            out.append(f"{indent}- 支线 {mark} {q['title']}" + (f"（问：{q['question']}）" if q["question"] else ""))
            if q["takeaway"]:
                out.append(f"{indent}  - 我的收获：{q['takeaway']}")
            elif q["gist"]:
                out.append(f"{indent}  - 讲解结论：{q['gist']}")
        return out

    for c in journey["chapters"]:
        state = {"done": "✓", "current": "→", "todo": "·"}[c["status"]]
        if c["status"] == "todo" and not c["side_quests"]:
            continue
        lines.append(f"### {state} 第 {c['n']} 章 · {c['label']}")
        if c["takeaway"]:
            lines.append(f"- 收获：{c['takeaway']}")
        for x in c["exchanges"]:
            if x["task"]:
                lines.append(f"- 任务：{x['task']}")
            lines.append(f"  - 我的回答：{x['text']}")
            if x["reply"]:
                lines.append(f"  - 教练：{x['reply']}")
        for mark in c["marks"][:4]:
            page = f"（第 {mark['page_index'] + 1} 页）" if isinstance(mark["page_index"], int) else ""
            lines.append(f"- 原文{page}：“{mark['quote']}”")
        lines += quests(c["side_quests"])
        lines.append("")
    if journey["other"]["side_quests"]:
        lines += ["### 主线之外", *quests(journey["other"]["side_quests"]), ""]
    return "\n".join(lines)

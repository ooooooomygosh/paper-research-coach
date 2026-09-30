from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from .store import Store

COMPARISON_FIELDS = [
    "problem",
    "unique_observation",
    "prior_assumption",
    "mechanism",
    "information",
    "objective",
    "dataset",
    "strongest_evidence",
    "failure_regime",
    "project_relation",
]


def location(anchor):
    if not anchor:
        return "待定位"
    return " · ".join(
        str(x)
        for x in [
            anchor.get("section"),
            anchor.get("figure"),
            f"PDF {anchor['page_index'] + 1}"
            if anchor.get("page_index") is not None
            else "",
            anchor.get("page_label"),
            anchor.get("status"),
        ]
        if x
    )


def paper_card(store: Store, paper_id: str):
    p = store.get("paper", paper_id)
    lines = [
        f"# {p['title']}",
        "",
        f"{p['authors']} | {p['year']}",
        f"{p.get('publication', '')}",
        f"DOI：{p['doi'] or '未核实或未分配'}",
        f"来源：{p['url']}",
        "",
        f"阅读目标：{p['goal']}",
        f"来源范围：{p['access_scope']}",
        "",
    ]
    lines += [
        f"- {field}: {p['comparison'].get(field) or '待核实'}"
        for field in COMPARISON_FIELDS
    ]
    for n in store.list("note", paper_id):
        lines += [
            "",
            f"## {n['provenance']} · {location(n.get('anchor'))}",
            "",
            n["content"],
            "",
            f"<!-- prc-note:{n['id']} revision:{n['revision']} -->",
        ]
    sessions = store.list("session", paper_id)
    if sessions:
        s = sessions[-1]
        lines += ["", "## 下次继续", "", s["pending_question"], s["next_action"]]
    return "\n".join(lines) + "\n"


def idea_cards(store: Store, paper_id: str):
    lines = ["# 研究问题", ""]
    for idea in store.list("idea", paper_id):
        lines += [f"## {idea['title']}", ""]
        for k in (
            "observation",
            "hypothesis",
            "alternative",
            "baseline",
            "minimal_test",
            "negative_outcome",
            "literature_question",
            "status",
        ):
            lines += [f"**{k}**", "", idea[k] or "待补充", ""]
    return "\n".join(lines)


def talk_outline(store: Store, paper_id: str):
    p = store.get("paper", paper_id)
    c = p["comparison"]
    sections = [
        ("0:00–0:45 听众为什么需要关心", ["problem", "project_relation"]),
        (
            "0:45–1:30 相比已有工作改变了什么",
            ["prior_assumption", "unique_observation"],
        ),
        ("1:30–2:45 核心机制与一张图", ["mechanism", "information"]),
        ("2:45–4:00 哪些证据支持结论", ["strongest_evidence", "objective"]),
        ("4:00–5:00 边界与后续问题", ["failure_regime", "project_relation"]),
    ]
    lines = [
        f"# {p['title']}：五分钟汇报提纲",
        "",
        "听众：请填写知识背景。根据听众调整前置知识与时间。",
        "",
    ]
    for title, fields in sections:
        lines += (
            [f"## {title}", ""]
            + [f"- {f}: {c.get(f) or '待核实后填写'}" for f in fields]
            + [""]
        )
    return "\n".join(lines)


def comparison_csv(store: Store):
    out = io.StringIO(newline="")
    fields = ["id", "title", "doi", *COMPARISON_FIELDS]
    writer = csv.DictWriter(out, fields)
    writer.writeheader()
    for p in store.list("paper"):
        row = {
            "id": p["id"],
            "title": p["title"],
            "doi": p["doi"],
            **{f: p["comparison"].get(f, "") for f in COMPARISON_FIELDS},
        }
        # Spreadsheet-safe text; original values remain unchanged in SQLite.
        writer.writerow(
            {
                k: "'" + v
                if isinstance(v, str) and v.startswith(("=", "+", "-", "@"))
                else v
                for k, v in row.items()
            }
        )
    return out.getvalue()


def annotated_pdf(store: Store, paper_id: str, destination: Path):
    from pypdf import PdfReader, PdfWriter
    from pypdf.annotations import Highlight, Text
    from pypdf.generic import ArrayObject, FloatObject

    p = store.get("paper", paper_id)
    if store.check_source(paper_id)["status"] != "current":
        raise ValueError(
            "The PDF is unavailable or has changed; reconcile its version first"
        )
    if destination.resolve() == Path(p["source_path"]).resolve():
        raise ValueError("Export must be separate from the source PDF")
    reader, writer = PdfReader(p["source_path"]), PdfWriter()
    writer.clone_document_from_reader(reader)
    skipped = []
    for n in store.list("note", paper_id):
        a = n.get("anchor")
        if (
            not a
            or a["status"] != "verified"
            or a["source_version"] != p["source_version"]
            or a["page_index"] is None
        ):
            skipped.append(n["id"])
            continue
        page = a["page_index"]
        content = f"{n['provenance']}: {n['content']}"
        if a["rects"]:
            rects = a["rects"]
            bounds = (
                min(r[0] for r in rects),
                min(r[1] for r in rects),
                max(r[2] for r in rects),
                max(r[3] for r in rects),
            )
            points = ArrayObject(
                [
                    FloatObject(v)
                    for x0, y0, x1, y1 in rects
                    for v in [x0, y1, x1, y1, x0, y0, x1, y0]
                ]
            )
            ann = Highlight(rect=bounds, quad_points=points, highlight_color="ffda75")
            from pypdf.generic import NameObject, TextStringObject

            ann[NameObject("/Contents")] = TextStringObject(content)
        else:
            box = reader.pages[page].cropbox
            x, y = float(box.left) + 20, float(box.top) - 40
            ann = Text(rect=(x, y, x + 20, y + 20), text=content, open=False)
        writer.add_annotation(page_number=page, annotation=ann)
    with destination.open("xb") as f:
        writer.write(f)
    return {"path": str(destination), "unplaced_note_ids": skipped}


def export(
    store: Store, kind: str, paper_id: str | None = None, output: str | None = None
):
    if kind != "comparison" and not paper_id:
        raise ValueError("Choose a paper")
    folder = store.root / "exports"
    folder.mkdir(exist_ok=True)
    from .models import uid

    suffix = ".pdf" if kind == "pdf" else ".csv" if kind == "comparison" else ".md"
    dest = (
        Path(output).expanduser().resolve()
        if output
        else folder / f"{paper_id or 'library'}-{kind}-{uid()[:8]}{suffix}"
    )
    if kind == "pdf":
        return annotated_pdf(store, paper_id, dest)
    handlers = {"paper": paper_card, "ideas": idea_cards, "talk": talk_outline}
    text = (
        comparison_csv(store)
        if kind == "comparison"
        else handlers[kind](store, paper_id)
    )
    with dest.open("x", encoding="utf-8", newline="") as f:
        f.write(text)
    return {"path": str(dest)}


def import_markdown(store: Store, paper_id: str, path: str):
    """Import the documented fallback format. Re-importing identical note IDs is a no-op."""
    import re

    source = Path(path).read_text(encoding="utf-8")
    blocks = re.findall(
        r"<!-- prc-note\s+(\{[^\n]+\})\s*-->\s*\n(.*?)\n<!-- /prc-note -->",
        source,
        re.S,
    )
    if not blocks:
        raise ValueError("No PRC note blocks found; see references/notebook.md")
    mutations = []
    for metadata, body in blocks:
        data = json.loads(metadata)
        data.update(paper_id=paper_id, content=body)
        if data.get("anchor") is not None:
            if data["anchor"].get("paper_id") not in (None, paper_id):
                raise ValueError("Imported anchor belongs to another paper")
            data["anchor"]["paper_id"] = paper_id
        try:
            prior = store.get("note", data["id"])
        except KeyError:
            mutations.append({"kind": "note", "data": data})
        else:
            if (
                prior["paper_id"] != paper_id
                or prior["content"] != body
                or prior["author"] != data.get("author", "user")
                or prior["provenance"] != data.get("provenance", "USER")
            ):
                raise ValueError(
                    "Existing note has different content; import as a new linked revision explicitly"
                )
    if len(mutations) > 100:
        raise ValueError("Import at most 100 new note blocks at a time")
    if mutations:
        store.commit({"mutations": mutations})
    return {"imported": len(mutations)}

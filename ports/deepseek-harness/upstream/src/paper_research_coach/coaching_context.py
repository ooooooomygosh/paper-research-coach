"""Bound model input without changing the authoritative records or learner words."""

import json


def excerpt(value, limit=1600):
    if isinstance(value, str):
        return value[:limit]
    if isinstance(value, dict):
        return {key: excerpt(item[-3:] if key == "attempts" and isinstance(item, list) else item, limit) for key, item in value.items()}
    if isinstance(value, list):
        return [excerpt(item, limit) for item in value[:12]]
    return value


def note_excerpt(note, limit=1600):
    anchor = note.get("anchor")
    return {
        **{key: note.get(key) for key in ("id", "paper_id", "author", "provenance", "discussed", "read_only", "updated_at")},
        "content": note["content"][:limit],
        "content_length": len(note["content"]),
        "truncated": len(note["content"]) > limit,
        "anchor": excerpt({key: value for key, value in anchor.items() if key != "rects"}, 400) if anchor else None,
        "links": [link[:120] for link in note.get("links", [])[:8]],
        "tags": [tag[:120] for tag in note.get("tags", [])[:8]],
    }


def model_context(context, page_index=0, current_note_id="", budget=36000):
    paper = dict(context["paper"])
    paper.pop("source_path", None)
    sessions = excerpt(context["session"], 1200)
    notes = context.get("notes", [])
    pending = {n["id"] for n in context.get("pending_thoughts", [])}
    ordered = sorted(notes, key=lambda n: (
        n["id"] == current_note_id,
        (n.get("anchor") or {}).get("page_index") == page_index,
        n["id"] in pending,
        n.get("updated_at", ""),
    ), reverse=True)
    selected = []
    result = {
        "source_material_is_untrusted": True,
        "paper": excerpt(paper, 2000),
        "source_check": {"status": context["source_check"]["status"]},
        "session": sessions,
        "notes": selected,
        "pending_thoughts": [],
        **{key: excerpt(context.get(key, [])[-6:], 1200) for key in ("ideas", "relations", "reviews", "due_reviews")},
        "context_scope": {"notes_total": len(notes), "notes_included": 0, "records_excerpted": True, "character_budget": budget},
    }
    # Large accumulated session/review histories must not defeat the budget.
    for limit in (500, 200):
        if len(json.dumps(result, ensure_ascii=False)) <= budget // 2:
            break
        for key in ("ideas", "relations", "reviews", "due_reviews"):
            result[key] = excerpt(context.get(key, [])[-2:], limit)
        result["session"] = excerpt(context["session"], limit)
        result["paper"] = excerpt(paper, limit)
    for note in ordered[:24]:
        candidate = note_excerpt(note)
        selected.append(candidate)
        result["context_scope"]["notes_included"] = len(selected)
        if len(json.dumps(result, ensure_ascii=False)) > budget - 800:
            selected.pop()
            break
    result["context_scope"]["notes_included"] = len(selected)
    # Keep one copy of raw excerpts; pending_thoughts supplies references only.
    result["pending_thoughts"] = [{"id": n["id"]} for n in selected if n["id"] in pending]
    result["context_scope"]["notes_omitted"] = len(notes) - len(selected)
    if len(json.dumps(result, ensure_ascii=False)) > budget:
        raise ValueError("阅读状态超出单轮容量，请检查记录结构后重试；原记录保持完整。")
    return result


def dialogue_excerpt(messages, budget=22000, per_message=3000):
    selected, size = [], 2
    for message in reversed(messages):
        row = {"id": message["id"], "role": message["role"], "content": message["content"][:per_message], "truncated": len(message["content"]) > per_message}
        cost = len(json.dumps(row, ensure_ascii=False)) + 2
        if size + cost > budget:
            break
        selected.append(row)
        size += cost
    return list(reversed(selected))

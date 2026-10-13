"""Branch explainer drafts: a short Markdown draft becomes typed JSON the workbench draws.

The model writes only content. This module validates the draft, returns line-numbered
errors the model can fix in one try, and runs a plain-writing check. The browser draws
the JSON; nobody hand-writes HTML, CSS or SVG, and no draft text is ever executed.

The draft syntax and the writing check follow the MIT-licensed "Answer me with HTML"
project (https://github.com/QingYunA/answer-me-with-html), reduced to what a reading
branch needs: flow, sequence, tree, timeline, callout, ask, kv, tables and math. A draft
written for that project renders here, and the other way round for these components.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

MAX_DRAFT = 16000
MAX_PANELS = 8
MAX_COMPONENTS = 12
COMPONENTS = ("flow", "sequence", "tree", "timeline", "callout", "ask", "kv")

EXAMPLES = {
    "flow": "```flow LR\n(Start) -> Check input: read\nCheck input -> {Valid?}\n{Valid?} -> Run: yes\n{Valid?} --> Stop: no\n```",
    "sequence": "```sequence\nClient -> Server: request\nServer --> Client: response\nnote Client, Server: connection open\n```",
    "tree": "```tree\nPaper\n  Method | what the authors built\n  *Evidence | the key figure\n```",
    "timeline": "```timeline\n2017 | Transformer paper | attention only\n*2020 | Scaling laws\n```",
    "callout": "```callout ok Short answer\nThe gain comes from the extra observations.\n```",
    "ask": "```ask\nWhich check do you want first?\n* Equal budget | fair comparison\n- Error bars | needs repeated runs\n```",
    "kv": "```kv cols=2\nQuestion: what changed?\nMethod: event trigger\n```",
}


class DraftError(ValueError):
    """A draft problem the model can fix: where it is and a correct example."""

    def __init__(self, message: str, line: int = 0, component: str = ""):
        self.line, self.component, self.detail = line, component, message
        text = (f"L{line} " if line else "") + (f"[{component}] " if component else "") + message
        if component in EXAMPLES:
            text += "\nCorrect example:\n" + EXAMPLES[component]
        super().__init__(text)


@dataclass
class Draft:
    doc: dict
    warnings: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------- draft structure

FENCE = re.compile(r"^(`{3,})\s*([A-Za-z][\w-]*)?\s*(.*)$")
ATTRS = re.compile(r"\s*\{[^}]*\}\s*$")


def parse_draft(text: str) -> Draft:
    text = text.replace("\r\n", "\n").strip("\n")
    if not text.strip():
        raise DraftError("the draft is empty")
    if len(text) > MAX_DRAFT:
        raise DraftError(f"the draft has {len(text)} characters (max {MAX_DRAFT}); keep 3 to 6 short panels")
    lines = text.split("\n")
    meta: dict[str, str] = {}
    start = 0
    if lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if end is None:
            raise DraftError("the front matter starts with --- but never closes", 1)
        for raw in lines[1:end]:
            if ":" in raw:
                key, value = raw.split(":", 1)
                meta[key.strip().lower()] = value.split(" #")[0].strip().strip("\"'")
        start = end + 1

    lead: list[dict] = []
    panels: list[dict] = []
    current = lead
    md: list[str] = []
    md_line = start + 1
    components = 0

    def flush():
        nonlocal md, md_line
        body = "\n".join(md).strip("\n")
        if body.strip():
            current.append({"type": "md", "text": body, "line": md_line})
        md = []

    i = start
    while i < len(lines):
        raw = lines[i]
        fence = FENCE.match(raw.strip())
        if fence:
            ticks, lang = fence.group(1), (fence.group(2) or "").lower()
            j = i + 1
            while j < len(lines) and not (
                lines[j].strip().startswith(ticks) and set(lines[j].strip()) == {"`"}
            ):
                j += 1
            if j >= len(lines):
                raise DraftError("a code fence is never closed", i + 1)
            body = "\n".join(lines[i + 1 : j])
            if lang in COMPONENTS:
                flush()
                components += 1
                if components > MAX_COMPONENTS:
                    raise DraftError(f"too many diagrams and components (max {MAX_COMPONENTS}); split the answer", i + 1)
                block = parse_component(lang, fence.group(3).strip(), body, i + 2)
                block["line"] = i + 1
                current.append(block)
            else:
                if not md:
                    md_line = i + 1
                md.extend(lines[i : j + 1])
            i = j + 1
            continue
        heading = re.match(r"^##\s+(.+?)\s*$", raw)
        if heading:
            flush()
            if len(panels) >= MAX_PANELS:
                raise DraftError(f"too many panels (max {MAX_PANELS}); cut panels or split the answer", i + 1)
            panel = {"title": ATTRS.sub("", heading.group(1)).strip(), "blocks": []}
            panels.append(panel)
            current = panel["blocks"]
        else:
            if not md:
                md_line = i + 1
            md.append(raw)
        i += 1
    flush()
    if not panels and not lead:
        raise DraftError("the draft has no content")

    title = meta.get("title") or (panels[0]["title"] if panels else "") or "讲解"
    sample = " ".join(b.get("text", "") for b in lead) + " ".join(
        b.get("text", "") for p in panels for b in p["blocks"]
    )
    doc = {
        "title": title[:120],
        "subtitle": meta.get("subtitle", "")[:200],
        "lang": meta.get("lang") or detect_lang(sample or title),
        "lead": lead,
        "panels": panels,
    }
    return Draft(doc=doc, warnings=lint(doc))


def detect_lang(text: str) -> str:
    cjk = len(re.findall(r"[㐀-鿿]", text))
    kana = len(re.findall(r"[぀-ヿ]", text))
    words = len(re.findall(r"[A-Za-z][A-Za-z'’-]*", text))
    if kana >= 3:
        return "ja"
    return "zh" if cjk >= 4 and cjk >= words / 2 else "en"


# ---------------------------------------------------------------- components


def content_lines(text: str, first: int):
    for k, raw in enumerate(text.split("\n")):
        t = raw.strip()
        if t and not t.startswith("//"):
            yield raw, t, first + k


def fields(text: str) -> list[str]:
    return [p.strip() for p in text.split("|")]


def parse_component(lang: str, args: str, body: str, first: int) -> dict:
    parser = {
        "flow": _flow, "sequence": _sequence, "tree": _tree, "timeline": _timeline,
        "callout": _callout, "ask": _ask, "kv": _kv,
    }[lang]
    block = parser(args, body, first)
    block["type"] = lang
    return block


BRACKETS = (("[(", ")]", "db"), ("[", "]", "rect"), ("(", ")", "round"), ("{", "}", "diamond"))
ARROW = re.compile(r"^\s*(-->|->)\s*")


def _flow(args, body, first):
    direction = next((w.upper() for w in args.split() if w.upper() in ("TB", "LR", "BT", "RL")), "TB")
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    groups: list[dict] = []

    def upsert(spec):
        prev = nodes.get(spec["id"])
        if not prev:
            nodes[spec["id"]] = spec
        else:
            if spec["explicit"]:
                prev["shape"] = spec["shape"]
            prev["hi"] = prev["hi"] or spec["hi"]
        return spec["id"]

    for _raw, t, line in content_lines(body, first):
        t = re.sub(r"^[+~-]\s+(?=\S)", "", t)  # change markers are not drawn here
        g = re.match(r"^group\s+(.+?)\s*[:：]\s*(.+)$", t, re.I)
        if g:
            groups.append({"name": g.group(1), "members": [m.strip() for m in re.split(r"[,，]", g.group(2)) if m.strip()], "line": line})
            continue
        chain, label = _chain(t, line)
        ids = [(arrow, [upsert(n) for n in group]) for arrow, group in chain]
        for k in range(1, len(ids)):
            for a in ids[k - 1][1]:
                for b in ids[k][1]:
                    edges.append({"from": a, "to": b, "dashed": ids[k][0] == "-->", "label": label if k == len(ids) - 1 else ""})
    if not nodes:
        raise DraftError("flow needs at least one node", first, "flow")
    for grp in groups:
        missing = [m for m in grp["members"] if m not in nodes]
        if missing:
            raise DraftError(f"group {grp['name']} refers to nodes that do not exist: {', '.join(missing)}", grp["line"], "flow")
    if len(nodes) > 30 or len(edges) > 60:
        raise DraftError(f"flow has {len(nodes)} nodes and {len(edges)} links (max 30 and 60); split it", first, "flow")
    return {
        "dir": direction,
        "nodes": [{k: v for k, v in n.items() if k != "explicit"} for n in nodes.values()],
        "edges": edges,
        "groups": [{"name": g["name"], "members": g["members"]} for g in groups],
    }


def _chain(t: str, line: int):
    chain, pos, arrow = [], 0, None
    while True:
        group = []
        while True:
            node, pos = _node(t, pos, line)
            group.append(node)
            amp = re.match(r"^\s*&\s*", t[pos:])
            if not amp:
                break
            pos += amp.end()
        chain.append((arrow, group))
        a = ARROW.match(t[pos:])
        if not a:
            break
        arrow = a.group(1)
        pos += a.end()
    rest = t[pos:].strip()
    if rest and not re.match(r"^[:：]", rest):
        raise DraftError(f'cannot parse "{t}". Write a link as A -> B: label', line, "flow")
    return chain, re.sub(r"^[:：]\s*", "", rest)


def _node(t: str, start: int, line: int):
    pos = start + len(re.match(r"^\s*", t[start:]).group(0))
    hi = pos < len(t) and t[pos] == "*"
    if hi:
        pos += 1
    shape, explicit = "rect", False
    for op, cl, kind in BRACKETS:
        if t.startswith(op, pos):
            close = t.find(cl, pos + len(op))
            if close == -1:
                raise DraftError(f"unclosed shape bracket, missing {cl}", line, "flow")
            label, end, shape, explicit = t[pos + len(op) : close].strip(), close + len(cl), kind, True
            break
    else:
        m = re.match(r"^(.*?)(?=\s*(?:-->|->|&|[:：]|$))", t[pos:])
        label, end = m.group(1).strip(), pos + m.end()
    if not label:
        raise DraftError(f'a node has no text in "{t}"', line, "flow")
    return {"id": label, "label": label, "shape": shape, "hi": hi, "explicit": explicit}, end


def _sequence(args, body, first):
    participants: list[str] = []
    steps: list[dict] = []

    def add(p):
        if p not in participants:
            participants.append(p)

    for _raw, t, line in content_lines(body, first):
        if m := re.match(r"^participants?\s*[:：]\s*(.+)$", t, re.I):
            for p in re.split(r"[,，]", m.group(1)):
                if p.strip():
                    add(p.strip())
        elif m := re.match(r"^note\s+([^:：]+)[:：]\s*(.+)$", t, re.I):
            over = [s.strip() for s in re.split(r"[,，]", m.group(1)) if s.strip()]
            for p in over:
                add(p)
            steps.append({"kind": "note", "over": over, "text": m.group(2).strip()})
        elif m := re.match(r"^==\s*(.+?)\s*==$", t):
            steps.append({"kind": "divider", "text": m.group(1)})
        elif m := re.match(r"^([^:：]+?)\s*(-->|->)\s*([^:：]+?)\s*(?:[:：]\s*(.*))?$", t):
            add(m.group(1).strip())
            add(m.group(3).strip())
            steps.append({"kind": "msg", "from": m.group(1).strip(), "to": m.group(3).strip(), "dashed": m.group(2) == "-->", "label": (m.group(4) or "").strip()})
        else:
            raise DraftError(f'cannot parse "{t}". Write a message as A -> B: label (--> is a dashed return) and a note as note A: text', line, "sequence")
    if len(participants) < 2:
        raise DraftError("sequence needs at least two participants", first, "sequence")
    if len(participants) > 8 or len(steps) > 40:
        raise DraftError(f"sequence has {len(participants)} participants and {len(steps)} steps (max 8 and 40)", first, "sequence")
    return {"participants": participants, "steps": steps, "numbered": bool(re.search(r"\bnum\b", args))}


def _tree(args, body, first):
    roots: list[dict] = []
    stack: list[tuple[int, dict]] = []
    count = 0
    for raw, t, line in content_lines(body, first):
        indent = len(raw.expandtabs(2)) - len(raw.expandtabs(2).lstrip())
        hi = t.startswith("*")
        text = t[1:].strip() if hi else t
        label, note = (fields(text) + [""])[:2]
        if not label:
            raise DraftError("a tree line needs a label before |", line, "tree")
        node = {"label": label, "note": note, "hi": hi, "children": []}
        while stack and stack[-1][0] >= indent:
            stack.pop()
        (stack[-1][1]["children"] if stack else roots).append(node)
        stack.append((indent, node))
        count += 1
    if not roots:
        raise DraftError("tree needs at least one node", first, "tree")
    if count > 60:
        raise DraftError(f"tree has {count} nodes (max 60); show the part that matters", first, "tree")
    return {"roots": roots, "list": bool(re.search(r"\blist\b", args))}


def _timeline(args, body, first):
    items = []
    for _raw, t, line in content_lines(body, first):
        parts = fields(t)
        if len(parts) < 2 or not parts[1]:
            raise DraftError(f'a timeline line must be time | title | note: "{t}"', line, "timeline")
        hi = parts[0].startswith("*")
        items.append({"when": parts[0].lstrip("*").strip(), "title": parts[1], "detail": parts[2] if len(parts) > 2 else "", "hi": hi})
    if not items:
        raise DraftError("timeline needs at least one item", first, "timeline")
    if len(items) > 14:
        raise DraftError(f"timeline has {len(items)} items (max 14)", first, "timeline")
    vertical = bool(re.search(r"\bv(ertical)?\b", args)) or (not re.search(r"\bh(orizontal)?\b", args) and len(items) > 6)
    return {"items": items, "vertical": vertical}


def _callout(args, body, first):
    kinds = {"info", "ok", "warn", "err"}
    word, *rest = args.split() or [""]
    kind = word if word in kinds else "info"
    title = " ".join(rest) if word in kinds else args.strip()
    if not title and not body.strip():
        raise DraftError("callout needs a title or a body", first, "callout")
    return {"kind": kind, "title": title, "text": body.strip(), "bodyLine": first}


def _ask(args, body, first):
    lines = list(content_lines(body, first))
    if not lines or re.match(r"^[*-]\s+", lines[0][1]):
        raise DraftError("the first line is the question", first, "ask")
    question = lines[0][1]
    options = []
    for _raw, t, line in lines[1:]:
        m = re.match(r"^([*-])\s+(.+)$", t)
        if not m:
            raise DraftError(f'"{t}" is not an option; start it with * (suggested) or -', line, "ask")
        label, note = (fields(m.group(2)) + [""])[:2]
        if not label:
            raise DraftError("an option needs a label before |", line, "ask")
        options.append({"label": label, "note": note, "suggested": m.group(1) == "*"})
    if not 2 <= len(options) <= 6:
        raise DraftError(f"write 2 to 6 options, not {len(options)}", first, "ask")
    multi = bool(re.search(r"(^|\s)multi(\s|$)", args))
    if not multi and sum(o["suggested"] for o in options) > 1:
        raise DraftError("a single-choice ask has more than one * option; keep one, or write `ask multi`", first, "ask")
    if len(question.split()) > 30 or len(question) > 120:
        raise DraftError("keep the question short (about 15 words)", first, "ask")
    return {"question": question, "options": options, "multi": multi}


def _kv(args, body, first):
    m = re.search(r"cols\s*=\s*(\d+)", args)
    cols = max(1, min(int(m.group(1)) if m else 2, 6))
    cells = []
    for _raw, t, line in content_lines(body, first):
        wide = t.startswith("*")
        text = t[1:].strip() if wide else t
        kv = re.match(r"^([^:：]+)[:：]\s*(.*)$", text)
        if not kv:
            raise DraftError(f'a line has no colon: "{t}"; expected key: value', line, "kv")
        cells.append({"key": kv.group(1).strip(), "value": kv.group(2).strip(), "wide": wide})
    if not cells:
        raise DraftError("kv needs at least one line", first, "kv")
    return {"cols": cols, "cells": cells}


# ---------------------------------------------------------------- plain-writing check
# Rules adapted from ASD-STE100 controlled writing: short sentences, one meaning per
# word, active voice, steps as commands. All findings are warnings; the draft is kept.

LIMITS = {"zh": {"procedural": 35, "descriptive": 45}, "en": {"procedural": 20, "descriptive": 25}}
MAX_SENTENCES = 6
ABBR = re.compile(r"\b(e\.g|i\.e|etc|vs|cf|approx|Fig|No)\.", re.I)
PASSIVE = re.compile(
    r"\b(?:am|is|are|was|were|be|been|being)\s+(?:\w+ly\s+)?(\w+ed|known|done|made|given|taken|seen|written|built|shown|sent|kept|held|found|set|put|run|begun|chosen|driven|broken)\b",
    re.I,
)
EN_WORDS = {
    "utilize": "use", "utilise": "use", "utilization": "use", "commence": "start", "commenced": "started",
    "prior to": "before", "in order to": "to", "approximately": "about", "ensure": "make sure",
    "replenish": "fill", "terminate": "stop", "facilitate": "help", "leverage": "use", "numerous": "many",
    "subsequently": "then", "endeavor": "try", "ascertain": "find", "sufficient": "enough",
    "demonstrate": "show", "assist": "help", "obtain": "get", "initiate": "start", "modify": "change",
    "possess": "have", "purchase": "buy", "in the event that": "if", "due to the fact that": "because",
    "at this point in time": "now", "a number of": "some", "with regard to": "about", "in addition": "also",
}
EN_RE = [
    (re.compile(r"\b" + re.sub(r"\s+", r"\\s+", w) + r"\b", re.I), s)
    for w, s in sorted(EN_WORDS.items(), key=lambda kv: -len(kv[0]))
]
UNIT = r"(?:个|次|秒|天|分钟|小时|倍|字|条|项|人|行|位|%|MB|GB|KB|TB|ms)?"
ZH_LIGHT_VERBS = [
    (re.compile(r"进行(?![中时])了?([一-龥]{2})"), "进行"),
    (re.compile(r"(?:加以|予以)([一-龥]{2})"), "加以/予以"),
    (re.compile(r"[做作]出了?([一-龥]{2})"), "做出"),
]
ZH_CLICHES = [
    "赋能", "抓手", "闭环", "打通", "全方位", "多维度", "深度融合", "显著提升", "至关重要", "不可或缺",
    "与此同时", "综上所述", "值得注意的是", "总而言之", "众所周知", "毋庸置疑", "一站式", "底层逻辑", "颗粒度", "方法论",
]
# (pattern, group that holds the flagged text, suggestion)
ZH_WORDS = [
    (re.compile("登陆"), 0, "登录"), (re.compile("帐号"), 0, "账号"), (re.compile("阀值"), 0, "阈值"),
    (re.compile("布署"), 0, "部署"), (re.compile("尽快"), 0, "说出具体期限"), (re.compile("若干"), 0, "写出数量"),
    (re.compile("大概|大约"), 0, "说明里用“约”，步骤里写具体数值"), (re.compile("多次"), 0, "写出次数"),
    (re.compile(r"\d\s*" + UNIT + r"\s*(以上|以下)"), 1, "写明端点：大于 / 不小于，小于 / 不大于"),
    (re.compile(r"\d[^。，；\n]{0,6}(以内)"), 1, "不超过"),
    (re.compile("单击|点按"), 0, "点击"), (re.compile("键入"), 0, "输入"), (re.compile("登出"), 0, "退出登录"),
    (re.compile("入参"), 0, "参数"), (re.compile("出参"), 0, "返回值"), (re.compile("缺省"), 0, "默认"),
]
PUNCT = "，。！？；：、（）「」『』“”‘’《》"


def is_cjk(c: str) -> bool:
    return "㐀" <= c <= "鿿" or "぀" <= c <= "ヿ"


def is_japanese(text: str) -> bool:
    return bool(re.search(r"[぀-ヿ]", text))


def split_sentences(text: str) -> list[str]:
    masked = ABBR.sub(lambda m: m.group(0).replace(".", "\0"), text)
    parts = re.findall(r"[^。！？；!?;]+?(?:[。！？；!?;]+|\.(?=\s|$)|$)|[^.]+?\.(?=\s|$)", masked)
    return [p.replace("\0", ".").strip() for p in parts if p.strip()]


def sentence_length(sentence: str) -> tuple[str, int]:
    cjk = sum(1 for c in sentence if is_cjk(c) and c not in PUNCT)
    words = len(re.findall(r"[A-Za-z0-9][\w'’-]*", sentence))
    return ("zh", cjk + words) if cjk >= 4 or cjk > words else ("en", words)


def strip_math(text: str) -> str:
    return re.sub(r"\$\$.*?\$\$|(?<!\\)\$[^$\n]+\$", " ", text, flags=re.S)


def clean(text: str) -> str:
    text = re.sub(r"~~[^~]*~~", "", text)
    text = re.sub(r"`[^`]*`", "", text)
    text = strip_math(text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"[*_]{1,3}", "", text)


def lint(doc: dict) -> list[dict]:
    out: list[dict] = []
    family = {"zh": "zh", "en": "en", "ja": "ja"}.get(doc.get("lang", ""), "neutral")
    blocks = list(doc["lead"]) + [b for p in doc["panels"] for b in p["blocks"]]
    for b in blocks:
        if b["type"] == "md":
            _lint_markdown(b["text"], b["line"], out, family)
        elif b["type"] == "callout" and b["text"]:
            _lint_markdown(b["text"], b["bodyLine"], out, family)
        elif b["type"] == "ask":
            _lint_markdown(
                "\n".join(["- " + b["question"]] + ["- " + ": ".join(x for x in (o["label"], o["note"]) if x) for o in b["options"]]),
                b["line"] + 1, out, family,
            )
    return out


def format_warning(w: dict) -> str:
    return f"L{w['line']} [{w['rule']}] {w['message']}" + (f" → {w['suggestion']}" if w.get("suggestion") else "")


def _lint_markdown(text: str, start: int, out: list[dict], family: str) -> None:
    para = None
    in_fence = in_math = False

    def flush():
        nonlocal para
        if para and para["count"] > MAX_SENTENCES:
            out.append({"line": para["line"], "rule": "paragraph-length", "message": f"paragraph has {para['count']} sentences (max {MAX_SENTENCES})"})
        para = None

    for i, raw in enumerate(text.split("\n")):
        line, t = start + i, raw.strip()
        if t.startswith("```"):
            in_fence = not in_fence
            flush()
            continue
        if in_fence:
            continue
        if in_math:
            if not t or t.endswith("$$"):
                in_math = False
            flush()
            continue
        if t.startswith("$$"):
            in_math = not (len(t) > 2 and t.endswith("$$"))
            flush()
            continue
        if not t or re.match(r"^#{1,6}\s", t) or re.match(r"^[-*_]{3,}$", t):
            flush()
            continue
        if t.startswith("|"):
            flush()
            if re.match(r"^\|?[\s:|-]+\|?$", t):
                continue
            cells = [c.strip() for c in t.strip("|").split("|")]
            if any(re.match(r"^(no|✗|✘)(\s|$)", c) for c in cells):
                continue
            for c in cells:
                _check_unit(clean(re.sub(r"^(ok|warn|✓|✔|⚠)(\s|$)", "", c)), line, "descriptive", out, family)
            continue
        item = re.match(r"^(?:([-*+])|(\d+)[.)])\s+(.*)$", t)
        if item:
            flush()
            _check_unit(clean(item.group(3)), line, "procedural" if item.group(2) else "descriptive", out, family)
            continue
        n = _check_unit(clean(re.sub(r"^>\s*", "", t)), line, "descriptive", out, family)
        para = para or {"line": line, "count": 0}
        para["count"] += n
    flush()


def _check_unit(text: str, line: int, kind: str, out: list[dict], family: str) -> int:
    sentences = split_sentences(text)
    zh_family = family == "zh"
    ja = family == "ja" or (zh_family and is_japanese(text))
    chinese_rules = zh_family and not ja
    english_rules = family != "neutral"  # English words inside Chinese text are checked too
    for s in sentences:
        lang, count = sentence_length(s)
        limit = LIMITS[lang][kind]
        if count > limit:
            unit = "characters" if lang == "zh" else "words"
            preview = s if len(s) <= 24 else s[:24] + "…"
            out.append({"line": line, "rule": "sentence-length", "message": f'{"step" if kind == "procedural" else "sentence"} has {count} {unit} (max {limit}): "{preview}"'})
        if english_rules and lang == "en" and (m := PASSIVE.search(s)):
            out.append({"line": line, "rule": "passive", "message": f'possible passive voice: "{m.group(0)}"', "suggestion": "use active voice"})
    found = []
    if english_rules:
        for rx, suggestion in EN_RE:
            found += [(m.start(), "word", f'not recommended: "{m.group(0)}"', suggestion) for m in rx.finditer(text)]
    if chinese_rules:
        for rx, label in ZH_LIGHT_VERBS:
            found += [(m.start(), "word", f'light verb "{m.group(0)}" ({label})', f'use "{m.group(1)}"') for m in rx.finditer(text)]
        for rx, group, suggestion in ZH_WORDS:
            found += [(m.start(group), "word", f'not recommended: "{m.group(group)}"', suggestion) for m in rx.finditer(text)]
    for _pos, rule, message, suggestion in sorted(found, key=lambda x: x[0]):
        out.append({"line": line, "rule": rule, "message": message, "suggestion": suggestion})
    if zh_family:
        for s in sentences:
            if not is_japanese(s) and s.count("的") >= 3:
                out.append({"line": line, "rule": "de-chain", "message": f"chained “的”: {s}", "suggestion": "split the sentence or remove extra “的”"})
        for c in ZH_CLICHES if chinese_rules else []:
            if c in text:
                out.append({"line": line, "rule": "cliche", "message": f"cliché “{c}”", "suggestion": "delete it or state a concrete fact"})
    return len(sentences)

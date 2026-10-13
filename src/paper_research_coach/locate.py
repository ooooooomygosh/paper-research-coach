"""Find where a quoted sentence sits on a PDF page, and search the paper's text.

The coach points the reader at the source: it may mark only words that really are on the
page. A quote is matched after light normalization (Unicode compatibility forms, curly
quotes, dashes, line-break hyphens, runs of whitespace, case), never by fuzzy guessing.
Rectangles come back in PDF user space (origin bottom-left), like `Anchor.rects`.
"""

from __future__ import annotations

import unicodedata

from .pdf_visual import _render_lock
from .store import Conflict

MAX_QUOTE = 600
MIN_QUOTE = 6
MAX_RECTS = 60
_SAME = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"', "″": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-",
    "\x02": "-",  # PDFium's mark for a hyphen at the end of a line
}
_DROP = {"\xad", "￾", "​", "‌", "‍", "﻿"}


def normalize(text: str) -> tuple[str, list[int]]:
    """Return a comparable form of `text` and, for each of its characters, the source index."""
    out: list[str] = []
    where: list[int] = []
    gap = None  # (start index, saw a line break) for a pending run of whitespace
    for index, raw in enumerate(text):
        if raw in _DROP:
            continue
        if raw.isspace() or unicodedata.category(raw) in ("Cc", "Zl", "Zp") and raw != "\x02":
            if gap is None:
                gap = (index, raw in "\r\n  ")
            elif raw in "\r\n  ":
                gap = (gap[0], True)
            continue
        chars = unicodedata.normalize("NFKC", _SAME.get(raw, raw)).lower()
        if gap is not None:
            # "observa-\ntions" reads as "observations"; any other gap is one space.
            joined = gap[1] and len(out) >= 2 and out[-1] == "-" and out[-2].isalpha() and chars[:1].isalpha()
            if joined:
                out.pop()
                where.pop()
            elif out:
                out.append(" ")
                where.append(gap[0])
            gap = None
        for c in chars:
            out.append(c)
            where.append(index)
    return "".join(out), where


def _squeeze(text: str, where: list[int]) -> tuple[str, list[int]]:
    """Drop spaces and hyphens: text extractors disagree about these far more than about letters."""
    keep = [(c, i) for c, i in zip(text, where) if c not in " -"]
    return "".join(c for c, _ in keep), [i for _, i in keep]


def match(page_text: str, quote: str) -> tuple[int, int] | None:
    """The first span of `page_text` (start, end exclusive, source indices) that reads as `quote`."""
    target, _ = normalize(quote)
    target = target.strip()
    if len(target) < MIN_QUOTE:
        return None
    text, where = normalize(page_text)
    at = text.find(target)
    if at < 0:
        text, where = _squeeze(text, where)
        target, _ = _squeeze(target, list(range(len(target))))
        at = text.find(target)
        if at < 0:
            return None
    return where[at], where[at + len(target) - 1] + 1


def _merge(rects):
    """Join neighbouring boxes on one line so a sentence draws as a few bands, not many glyphs."""
    merged: list[list[float]] = []
    for x0, y0, x1, y1 in rects:
        if x1 - x0 <= 0 or y1 - y0 <= 0:
            continue
        last = merged[-1] if merged else None
        if last and abs(last[1] - y0) < 2 and abs(last[3] - y1) < 2 and x0 - last[2] < 12:
            last[0], last[1], last[2], last[3] = min(last[0], x0), min(last[1], y0), max(last[2], x1), max(last[3], y1)
        else:
            merged.append([x0, y0, x1, y1])
    return [tuple(round(v, 2) for v in r) for r in merged[:MAX_RECTS]]


def _open(store, paper_id):
    paper = store.get("paper", paper_id)
    if store.check_source(paper_id)["status"] != "current":
        raise Conflict("请先核实当前 PDF 版本。")
    return paper


def page_quotes(store, paper_id: str, page_index: int, quotes: list[str]) -> dict:
    """Rectangles for each quote on one page. A quote that is not on the page is reported, not guessed."""
    paper = _open(store, paper_id)
    if not 0 <= page_index < paper["page_count"]:
        raise ValueError("页码超出当前 PDF 范围。")
    found, missing = [], []
    with _render_lock:
        import pypdfium2 as pdfium

        try:
            with pdfium.PdfDocument(paper["source_path"]) as document:
                page = document[page_index]
                textpage = page.get_textpage()
                try:
                    count = textpage.count_chars()
                    text = textpage.get_text_range(0, count) if count else ""
                    for quote in quotes:
                        span = match(text, quote[:MAX_QUOTE]) if text.strip() else None
                        if not span:
                            missing.append(quote)
                            continue
                        start, end = span
                        n = textpage.count_rects(start, end - start)
                        rects = _merge([textpage.get_rect(i) for i in range(n)])
                        if rects:
                            found.append({"quote": quote, "rects": rects})
                        else:
                            missing.append(quote)
                finally:
                    textpage.close()
                    page.close()
        except (RuntimeError, OSError):
            raise ValueError("当前页的文字未能读取，请检查 PDF 文件后重试。") from None
    if store.get("paper", paper_id)["source_version"] != paper["source_version"]:
        raise Conflict("PDF 在查看期间已改变，请重新核实。")
    return {"page_index": page_index, "source_version": paper["source_version"],
            "has_text": bool(text.strip()), "found": found, "missing": missing}


def search(store, paper_id: str, query: str, limit: int = 12, per_page: int = 3) -> dict:
    """Pages whose text contains `query` (same normalization), with short snippets."""
    paper = _open(store, paper_id)
    target, _ = normalize(query)
    target = target.strip()
    if len(target) < 2:
        raise ValueError("搜索词太短。")
    hits, empty = [], 0
    with _render_lock:
        import pypdfium2 as pdfium

        try:
            with pdfium.PdfDocument(paper["source_path"]) as document:
                for index in range(len(document)):
                    page = document[index]
                    textpage = page.get_textpage()
                    try:
                        count = textpage.count_chars()
                        text = textpage.get_text_range(0, count) if count else ""
                    finally:
                        textpage.close()
                        page.close()
                    if not text.strip():
                        empty += 1
                        continue
                    flat, where = normalize(text)
                    at, on_page = flat.find(target), 0
                    while at >= 0 and on_page < per_page and len(hits) < limit:
                        start, end = where[at], where[at + len(target) - 1] + 1
                        before = " ".join(text[max(0, start - 90):start].split())
                        after = " ".join(text[end:end + 140].split())
                        hits.append({"page_index": index, "snippet": ("…" if start > 90 else "") + before + " [" + " ".join(text[start:end].split()) + "] " + after + "…"})
                        on_page += 1
                        at = flat.find(target, at + len(target))
                    if len(hits) >= limit:
                        break
        except (RuntimeError, OSError):
            raise ValueError("PDF 文字未能读取，请检查文件后重试。") from None
    return {"query": query, "hits": hits, "pages_without_text": empty, "untrusted_source": True,
            "truncated": len(hits) >= limit}

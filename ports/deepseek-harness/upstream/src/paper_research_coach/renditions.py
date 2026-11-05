"""Resolve versioned translated PDF positions without treating them as source geometry."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path


@lru_cache(maxsize=32)
def _inspect(path: str, size: int, mtime: int, ctime: int):
    from pypdf import PdfReader

    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
        stream.seek(0)
        reader = PdfReader(stream)
        boxes = [tuple(float(v) for v in page.mediabox) for page in reader.pages]
    return {"document_version": digest.hexdigest(), "page_count": len(boxes), "boxes": boxes}


def inspect_pdf(path: Path):
    stat = path.stat()
    return _inspect(str(path.resolve()), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def rendition_file(root: Path, job: dict, view: str):
    if view not in ("mono", "dual") or not job.get("artifacts", {}).get(view):
        raise ValueError("译文 PDF 尚未生成。")
    folder = (root / "translations" / job["id"]).resolve()
    path = Path(job["artifacts"][view]).resolve()
    if not folder.is_relative_to((root / "translations").resolve()) or not path.is_relative_to(folder):
        raise ValueError("译文文件位置无效。")
    return path


def resolve_rendition(root, db, paper, source_version, rendition):
    table = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='translation_jobs'").fetchone()
    row = db.execute("SELECT data FROM translation_jobs WHERE id=?", (rendition.job_id,)).fetchone() if table else None
    if not row:
        raise ValueError("这条批注对应的译文不存在。")
    job = json.loads(row[0])
    if job["paper_id"] != paper["id"] or job["source_version"] != source_version:
        raise ValueError("批注与译文不属于同一篇论文版本。")
    path = rendition_file(root, job, rendition.view)
    info = inspect_pdf(path)
    if info["document_version"] != rendition.document_version:
        raise ValueError("译文 PDF 已改变，请重新核实批注位置。")
    if rendition.page_index >= info["page_count"]:
        raise ValueError("批注页码超出译文 PDF 范围。")
    left, bottom, right, top = info["boxes"][rendition.page_index]
    for x0, y0, x1, y1 in rendition.rects:
        if x0 < left - 1 or y0 < bottom - 1 or x1 > right + 1 or y1 > top + 1:
            raise ValueError("批注位置超出译文页面。")
    return path

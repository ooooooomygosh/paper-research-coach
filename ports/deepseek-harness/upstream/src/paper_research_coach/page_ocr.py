"""On-device OCR for individual pages. Cached text is bound to the source digest."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading

from filelock import FileLock

from .pdf_visual import _render_lock
from .store import Conflict, cached_digest


_slots = threading.BoundedSemaphore(2)


def _engine():
    if sys.platform == "darwin":
        return "Apple Vision"
    if shutil.which("tesseract"):
        return "Tesseract"
    raise ValueError("本机未找到 OCR 引擎。请安装 Tesseract 和所需语言包。")


def _recognize(path, index, engine, lang):
    import pypdfium2 as pdfium

    with tempfile.TemporaryDirectory(prefix="prc-page-") as folder:
        image = Path(folder) / "page.png"
        with _render_lock, pdfium.PdfDocument(path) as document:
            if not 0 <= index < len(document):
                raise ValueError("页码超出范围。")
            page = document[index]
            width, height = page.get_size()
            if min(width, height) <= 0:
                raise ValueError("页面尺寸无效。")
            bitmap = page.render(scale=min(3.0, 2600 / max(width, height)), grayscale=True)
            try:
                bitmap.to_pil().save(image, compress_level=1)
            finally:
                bitmap.close()
                page.close()
        if engine == "Apple Vision":
            command = ["/usr/bin/osascript", "-l", "JavaScript", str(Path(__file__).with_name("vision_ocr.js")), str(image)]
        else:
            command = ["tesseract", str(image), "stdout", "-l", lang]
        try:
            proc = subprocess.run(command, capture_output=True, timeout=90, check=True)
        except (OSError, subprocess.SubprocessError) as exc:
            raise ValueError(f"{engine} 识别失败或超时，请检查本机 OCR 引擎及语言包。") from exc
        return proc.stdout.decode("utf-8").strip()


def recognize_page(path: Path, index: int, version: str, cache: Path):
    engine = _engine()
    lang = os.environ.get("PRC_OCR_LANG", "eng") if engine == "Tesseract" else "zh-Hans+zh-Hant+en-US"
    key = hashlib.sha256(f"v1:{version}:{index}:{engine}:{lang}".encode()).hexdigest()
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    entry = cache / (key + ".txt")
    with FileLock(str(cache / (key[:2] + ".lock"))), _slots:
        if cached_digest(path) != version:
            raise Conflict("PDF 已更新。请重新核实来源。")
        cached = entry.exists()
        if cached:
            text = entry.read_text(encoding="utf-8")
        else:
            text = _recognize(path, index, engine, lang)
            if cached_digest(path) != version:
                raise Conflict("识别期间 PDF 已更新。")
            tmp = entry.with_suffix(".tmp")
            tmp.write_text(text, encoding="utf-8")
            tmp.replace(entry)
    return {"text": text, "page_index": index, "source_version": version, "engine": engine, "cached": cached}


def fill_scanned_pages(path, pages, mode, cache):
    """Keep native text on mixed documents and preserve every page boundary."""
    if mode == "off":
        return False
    missing = [index for index, text in enumerate(pages) if mode == "force" or not text.strip()]
    if not missing:
        return False
    version = cached_digest(path)
    used = False
    for index in missing:
        try:
            text = recognize_page(path, index, version, cache)["text"]
        except ValueError as error:
            print(f"OCR page {index + 1}: {error}", file=sys.stderr)
            continue
        if text:
            pages[index] = text
            used = True
    return used

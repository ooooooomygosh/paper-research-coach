"""Render a verified paper page for the coach without changing the source PDF."""

import base64
import io
import threading

from .store import Conflict

# PDFium requires serialized calls even when different documents are rendered.
_render_lock = threading.Lock()


def view_page(store, paper_id, page_index):
    paper = store.get("paper", paper_id)
    if store.check_source(paper_id)["status"] != "current":
        raise Conflict("请先核实当前 PDF 版本。")
    if not 0 <= page_index < paper["page_count"]:
        raise ValueError("页码超出当前 PDF 范围。")
    with _render_lock:
        import pypdfium2 as pdfium

        try:
            with pdfium.PdfDocument(paper["source_path"]) as document:
                page = document[page_index]
                width, height = page.get_size()
                if min(width, height) <= 0:
                    raise ValueError("无效页面尺寸")
                bitmap = page.render(scale=min(2.5, 1800 / max(width, height)))
                try:
                    picture = bitmap.to_pil()
                    stream = io.BytesIO()
                    picture.save(stream, format="PNG")
                    mime = "image/png"
                    if stream.tell() > 2_500_000:
                        stream = io.BytesIO()
                        picture.convert("RGB").save(stream, format="JPEG", quality=85)
                        mime = "image/jpeg"
                finally:
                    bitmap.close()
                    page.close()
        except (RuntimeError, ValueError, OSError):
            raise ValueError("当前页未能渲染，请检查 PDF 文件后重试。") from None
    if store.get("paper", paper_id)["source_version"] != paper["source_version"] or store.check_source(paper_id)["status"] != "current":
        raise Conflict("PDF 在查看期间已改变，请重新核实。")
    return {
        "page_index": page_index,
        "source_version": paper["source_version"],
        "untrusted_source": True,
        "image_url": f"data:{mime};base64," + base64.b64encode(stream.getvalue()).decode(),
    }

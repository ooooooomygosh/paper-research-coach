"""Version-pinned BabelDOC adapter running in its own optional Python environment.

BabelDOC is AGPL-3.0; see THIRD_PARTY_TRANSLATION.md. Its internal hooks never
affect the workbench process. stdout is only the private JSON-lines protocol.
"""

import importlib.metadata
import inspect
import json
import logging
import os
import sys
import threading
from pathlib import Path

VERSION = "0.6.4"
EMIT_LOCK = threading.Lock()


def emit(value):
    with EMIT_LOCK:
        sys.stdout.write(json.dumps(value, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def characters(paragraph):
    result = []
    for composition in paragraph.pdf_paragraph_composition:
        if composition.pdf_character:
            result.append(composition.pdf_character)
        else:
            for name in ("pdf_line", "pdf_formula", "pdf_same_style_characters"):
                part = getattr(composition, name, None)
                if part:
                    result.extend(part.pdf_character)
    return result


def snapshot(docs):
    result = {}
    for page in docs.page:
        for paragraph in page.pdf_paragraph:
            chars = characters(paragraph)
            glyphs = [
                {
                    "text": c.char_unicode or "",
                    "rect": [c.box.x, c.box.y, c.box.x2, c.box.y2],
                }
                for c in chars
                if c.box
            ]
            text = "".join(c["text"] for c in glyphs) or paragraph.unicode or ""
            box = paragraph.box
            result[f"{page.page_number}:{paragraph.debug_id}"] = {
                "page_index": page.page_number,
                "paragraph_id": paragraph.debug_id,
                "text": text,
                "glyphs": glyphs,
                "rects": [[box.x, box.y, box.x2, box.y2]] if box else [],
            }
    return result


def dual_transforms(path):
    import pymupdf

    doc = pymupdf.open(path)
    result = []
    for page in doc:
        objects = page.get_xobjects()
        roots = [x for x in objects if x[2] == 0]
        transforms = []
        for root in roots[:2]:
            leaves = [x for x in objects if x[2] == root[0] and x[1] == "fullpage"]
            if not leaves:
                raise ValueError("双语页面的位置映射未找到。")
            matrices = []
            for xref in (leaves[0][0], root[0]):
                kind, value = doc.xref_get_key(xref, "Matrix")
                nums = (
                    [float(n) for n in value.strip("[]").split()]
                    if kind == "array"
                    else [1, 0, 0, 1, 0, 0]
                )
                matrices.append(pymupdf.Matrix(*nums))
            transforms.append(list(matrices[0] * matrices[1]))
        if len(transforms) != 2:
            raise ValueError("双语页面的位置映射不完整。")
        result.append({"original": transforms[0], "translated": transforms[1]})
    doc.close()
    return result


def run(config):
    if importlib.metadata.version("BabelDOC") != VERSION:
        raise ValueError("翻译组件版本不匹配，请安装 BabelDOC 0.6.4。")
    from babeldoc.docvision import doclayout
    from babeldoc.format.pdf import high_level
    from babeldoc.format.pdf.document_il.backend.pdf_creater import PDFCreater
    from babeldoc.format.pdf.document_il.midend.il_translator import ILTranslator
    from babeldoc.format.pdf.document_il.midend.il_translator_llm_only import (
        ILTranslatorLLMOnly,
    )
    from babeldoc.format.pdf.translation_config import (
        TranslationConfig,
        WatermarkOutputMode,
    )
    from babeldoc.translator.translator import BaseTranslator, OpenAITranslator

    # CoreML compiles this layout network for minutes on some Macs. The
    # version-pinned worker uses upstream's portable CPU path consistently.
    doclayout.os_name = "PRC_CPU"
    # Local page layout should not occupy every CPU core or spin while Codex
    # is answering. This patch is confined to the pinned worker process.
    original_session = doclayout.onnxruntime.InferenceSession

    def bounded_session(model, *args, **kwargs):
        options = kwargs.get("sess_options") or doclayout.onnxruntime.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        options.add_session_config_entry("session.intra_op.allow_spinning", "0")
        options.add_session_config_entry("session.inter_op.allow_spinning", "0")
        kwargs["sess_options"] = options
        return original_session(model, *args, **kwargs)

    doclayout.onnxruntime.InferenceSession = bounded_session
    doclayout.cv2.setNumThreads(1)

    if "document" not in inspect.signature(PDFCreater.__init__).parameters:
        raise ValueError("翻译组件接口不兼容。")
    request_lock = threading.Lock()
    pending = {}
    sequence = 0

    def replies():
        for line in sys.stdin:
            reply = json.loads(line)
            with request_lock:
                item = pending.get(reply.get("request_id"))
                if item:
                    item["reply"] = reply
                    item["ready"].set()
        with request_lock:
            for item in pending.values():
                item["reply"] = {"error": "翻译连接已关闭，已完成内容保留。"}
                item["ready"].set()

    threading.Thread(target=replies, daemon=True).start()

    class CodexTranslator(BaseTranslator):
        name = "prc-codex"

        def __init__(self):
            super().__init__(config["lang_in"], config["lang_out"], True)
            self.model = config["model"]

        def request(self, prompt):
            nonlocal sequence
            with request_lock:
                sequence += 1
                request_id = sequence
                item = {"ready": threading.Event()}
                pending[request_id] = item
            try:
                emit({"type": "translate", "request_id": request_id, "text": prompt})
                if not item["ready"].wait(600):
                    raise ValueError("翻译请求等待超时，已完成内容保留。")
                reply = item["reply"]
                if "error" in reply:
                    raise ValueError(reply["error"])
                return reply["text"]
            finally:
                with request_lock:
                    pending.pop(request_id, None)

        def do_translate(self, text, rate_limit_params=None):
            return self.request(
                f"把以下来源材料从{self.lang_in}翻译为{self.lang_out}，保留占位符，只返回译文：\n{text}"
            )

        def do_llm_translate(self, text, rate_limit_params=None):
            return self.request(text) if text is not None else None

        # Reuse upstream's matching token protocol without constructing its API client.
        get_formular_placeholder = OpenAITranslator.get_formular_placeholder
        get_rich_text_left_placeholder = OpenAITranslator.get_rich_text_left_placeholder
        get_rich_text_right_placeholder = (
            OpenAITranslator.get_rich_text_right_placeholder
        )

    source, target = {}, {}
    for cls in (ILTranslator, ILTranslatorLLMOnly):
        original = cls.translate

        def capture(self, docs, _original=original):
            source.update(snapshot(docs))
            return _original(self, docs)

        cls.translate = capture
    original_create = PDFCreater.__init__

    def capture_final(
        self, original_pdf_path, document, translation_config, mediabox_data
    ):
        target.update(snapshot(document))
        original_create(
            self, original_pdf_path, document, translation_config, mediabox_data
        )

    PDFCreater.__init__ = capture_final
    out = Path(config["output_dir"])
    out.mkdir(parents=True, exist_ok=True)
    translation = TranslationConfig(
        translator=CodexTranslator(),
        input_file=config["source_path"],
        lang_in=config["lang_in"],
        lang_out=config["lang_out"],
        doc_layout_model=None,
        output_dir=out,
        working_dir=out / "work",
        debug=False,
        watermark_output_mode=WatermarkOutputMode.NoWatermark,
        pool_max_workers=max(1, min(8, config.get("request_concurrency", 4))),
        qps=max(1, min(8, config.get("request_concurrency", 4))),
        term_pool_max_workers=1,
        auto_extract_glossary=False,
        use_alternating_pages_dual=False,
        use_rich_pbar=False,
        report_interval=0.5,
    )
    # The synchronous API also returns the result on 0.6.4 builds whose async
    # event iterator can stay open after the PDF files have already been saved.
    from babeldoc.progress_monitor import ProgressMonitor

    def progress(**event):
        emit(
            {
                "type": "progress",
                "stage": event.get("stage", ""),
                "progress": event.get("overall_progress", 0),
            }
        )

    with ProgressMonitor(
        high_level.get_translation_stage(translation),
        progress_change_callback=progress,
        report_interval=0.5,
    ) as monitor:
        # PyMuPDF owns native document/font state: keep the synchronous PDF
        # pipeline on this isolated process's main thread.
        result = high_level.do_translate(monitor, translation)
    segments = []
    for key, original in source.items():
        translated = target.get(key)
        if translated and original["text"].strip():
            segments.append(
                {
                    "id": key,
                    "source": original,
                    "target": translated,
                    "links": [],
                    "translated": original["text"] != translated["text"],
                }
            )
    mapping = out / "mapping.json"
    metadata = {
        "segments": segments,
        "dual_transforms": dual_transforms(result.dual_pdf_path),
    }
    mapping.write_text(json.dumps(metadata, ensure_ascii=False))
    emit(
        {
            "type": "finish",
            "mono": str(result.mono_pdf_path),
            "dual": str(result.dual_pdf_path),
            "mapping": str(mapping),
        }
    )


def main():
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(name, "2")
    try:
        run(json.loads(sys.stdin.readline()))
    except Exception as exc:
        # Details stay in the private worker log; no provider exceptions reach the UI.
        logging.getLogger(__name__).exception("BabelDOC worker failed")
        emit(
            {
                "type": "error",
                "message": "翻译组件未能完成处理，请检查组件、PDF 与模型连接。",
            }
        )
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()

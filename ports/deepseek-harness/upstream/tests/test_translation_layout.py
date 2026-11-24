import pytest

from paper_research_coach.translation_layout import TranslationLayoutError, validate_pdf_layout


def render_pdf(engine, path, overlays=0, page_count=1):
    with engine.open() as document:
        for _ in range(page_count):
            page = document.new_page(width=380, height=400)
            for row in range(12):
                baseline = 40 + 24 * row
                page.insert_text((40, baseline), "Measurements at the receiving station")
                if row < overlays:
                    page.insert_text((47, baseline + 3), "Overlapping unrelated text in the same column")
        document.save(path)


def test_layout_gate_detects_persistent_overlap_above_original(tmp_path):
    engine = pytest.importorskip("pymupdf")
    source = tmp_path / "source.pdf"
    mono = tmp_path / "mono.pdf"
    dual = tmp_path / "dual.pdf"
    render_pdf(engine, source)
    render_pdf(engine, mono, overlays=12)
    render_pdf(engine, dual)
    with pytest.raises(TranslationLayoutError, match="第 1 页.*叠字"):
        validate_pdf_layout(source, mono, dual)

    # Similar geometry in the original is not evidence of a translation defect.
    validate_pdf_layout(mono, mono, dual)
    render_pdf(engine, mono, overlays=1)
    validate_pdf_layout(source, mono, dual)

    render_pdf(engine, dual, page_count=2)
    with pytest.raises(TranslationLayoutError, match="页数不一致"):
        validate_pdf_layout(source, mono, dual)

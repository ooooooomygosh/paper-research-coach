from hashlib import sha256
from importlib import import_module

import pytest

pytest.importorskip("babeldoc")
pymupdf = pytest.importorskip("pymupdf")
pdf_translation_input = import_module("paper_research_coach.pdf_translation_input")


VISIBLE = b"""BT /helv 12 Tf 1 0 0 1 55 210 Tm (Current caption) Tj ET
q 40 100 100 80 re W* n
BT /helv 12 Tf 1 0 0 1 48 136 Tm (Visible label) Tj ET Q
q 40 100 100 80 re W n
BT /helv 12 Tf 1 0 0 1 129 108 Tm (Partly clipped) Tj ET Q
"""
HIDDEN = b"""/PlacedPDF <<>> BDC
q 40 100 100 80 re W n
BT /helv 12 Tf 1 0 0 1 48 260 Tm (Unused draft title) Tj
1 0 0 1 48 48 Tm (Unused draft body) Tj ET EMC Q
"""


def add_content(page, content):
    pdf = page.parent
    xref = pdf.get_new_xref()
    pdf.update_object(xref, "<<>>")
    pdf.update_stream(xref, content)
    contents = " ".join(f"{ref} 0 R" for ref in [*page.get_contents(), xref])
    pdf.xref_set_key(page.xref, "Contents", f"[{contents}]")


def make_pdf(path, *, hidden=True, layer=False):
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=300, height=300)
        page.insert_font(fontname="helv")
        image = b"P6\n2 2\n255\n" + bytes(
            (255, 0, 0, 0, 255, 0, 0, 0, 255, 255, 255, 0)
        )
        page.insert_image(pymupdf.Rect(54, 122, 100, 160), stream=image)
        # Separate streams exercise the graphics-state and resource handling.
        add_content(page, VISIBLE)
        if hidden:
            add_content(page, HIDDEN)
        page.set_cropbox(pymupdf.Rect(10, 12, 288, 290))
        page.set_rotation(90)
        page = pdf.new_page(width=300, height=300)
        page.insert_text((50, 50), "Page two")
        if layer:
            pdf.add_ocg("Document layer")
        pdf.save(path)


def trace_text(page):
    return "".join(
        chr(char[0]) for span in page.get_texttrace() for char in span["chars"]
    )


def test_drops_fully_clipped_draft_but_keeps_figure_and_visible_spans(tmp_path):
    original = tmp_path / "placed-pdf.pdf"
    make_pdf(original)
    original_digest = sha256(original.read_bytes()).digest()

    normalized = pdf_translation_input.prepare_translation_input(
        original, tmp_path / "work"
    )

    assert normalized != original
    assert normalized.name == original.name
    assert sha256(original.read_bytes()).digest() == original_digest
    with pymupdf.open(original) as source, pymupdf.open(normalized) as prepared:
        assert len(source) == len(prepared) == 2
        for before, after in zip(source, prepared):
            assert before.mediabox == after.mediabox
            assert before.cropbox == after.cropbox
            assert before.rotation == after.rotation
            assert before.get_text("words") == after.get_text("words")
            assert before.get_images() == after.get_images()
            assert (
                before.get_pixmap(dpi=144).samples == after.get_pixmap(dpi=144).samples
            )

        assert "Unused draft title" in trace_text(source[0])
        assert "Unused draft" not in trace_text(prepared[0])
        assert "Current caption" in trace_text(prepared[0])
        assert "Visible label" in trace_text(prepared[0])
        assert "Partly clipped" in trace_text(prepared[0])
        assert prepared[1].read_contents() == source[1].read_contents()
        assert not prepared.get_ocgs()


@pytest.mark.parametrize("layer", [False, True])
def test_passes_through_without_verified_draft_blocks(tmp_path, layer):
    original = tmp_path / "original.pdf"
    make_pdf(original, hidden=layer, layer=layer)
    work = tmp_path / "work"

    assert pdf_translation_input.prepare_translation_input(original, work) == original
    assert not work.exists()


def test_visual_check_rejects_a_changed_page(tmp_path, monkeypatch):
    original = tmp_path / "original.pdf"
    make_pdf(original)
    work = tmp_path / "work"
    monkeypatch.setattr(
        pdf_translation_input, "fully_clipped_blocks", lambda _, __, blocks: blocks
    )

    assert pdf_translation_input.prepare_translation_input(original, work) == original
    assert not work.exists()


def test_does_not_render_pages_above_the_pixel_budget(tmp_path, monkeypatch):
    original = tmp_path / "original.pdf"
    make_pdf(original)
    monkeypatch.setattr(pdf_translation_input, "MAX_VERIFICATION_PIXELS", 1)

    def fail_render(*args, **kwargs):
        pytest.fail("oversized page should have been skipped")

    monkeypatch.setattr(pymupdf.Page, "get_pixmap", fail_render)
    assert (
        pdf_translation_input.prepare_translation_input(original, tmp_path / "work")
        == original
    )

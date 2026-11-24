from importlib import import_module

import pytest

pytest.importorskip("babeldoc")
il = import_module("babeldoc.format.pdf.document_il.il_version_1")
repair = import_module("paper_research_coach.translation_typesetting")


def characters(text, x, y, render_order):
    result = []
    for i, value in enumerate(text):
        box = il.Box(x + i * 4, y, x + i * 4 + 3.9, y + 7)
        result.append(
            il.PdfCharacter(
                char_unicode=value,
                box=box,
                visual_bbox=il.VisualBbox(box=box),
                xobj_id=0,
                render_order=render_order + i,
            )
        )
    return result


def author_paragraphs(finder):
    name = characters("A. Author (a@research", 20, 100, 11)
    dot = characters(".", name[-1].box.x2 + 0.1, 100, name[-1].render_order + 1)
    start = characters(
        "edu) studies optics.", dot[-1].box.x2 + 0.1, 100, dot[-1].render_order + 1
    )
    body = characters("Her laboratory wins.", 20, 90, start[-1].render_order + 1)
    paragraphs = [
        il.PdfParagraph(
            pdf_paragraph_composition=[finder.create_line(line) for line in lines],
            unicode=" ".join("".join(c.char_unicode for c in line) for line in lines),
            layout_id=1 if len(lines[0]) > 1 else 2,
        )
        for lines in ([name], [dot], [start, body])
    ]
    for paragraph in paragraphs:
        finder.update_paragraph_data(paragraph)
    return paragraphs


@pytest.mark.parametrize("one_composition", [False, True])
def test_visible_email_is_joined_with_original_glyphs_and_body_lines(one_composition):
    finder = object.__new__(repair.ParagraphFinder)
    page = il.Page(pdf_paragraph=author_paragraphs(finder))
    original = [
        char
        for paragraph in page.pdf_paragraph
        for comp in paragraph.pdf_paragraph_composition
        for char in comp.pdf_line.pdf_character
    ]
    suffix = page.pdf_paragraph[-1]
    email_end, saved_body = suffix.pdf_paragraph_composition
    if one_composition:
        suffix.pdf_paragraph_composition = [
            finder.create_line(
                email_end.pdf_line.pdf_character + saved_body.pdf_line.pdf_character
            )
        ]
        finder.update_paragraph_data(suffix)

    repair.restore_split_email_paragraphs(finder, page)

    (paragraph,) = page.pdf_paragraph
    assert (
        paragraph.unicode
        == "A. Author (a@research.edu) studies optics. Her laboratory wins."
    )
    if not one_composition:
        assert paragraph.pdf_paragraph_composition[-1] is saved_body
    recorded = [
        char
        for comp in paragraph.pdf_paragraph_composition
        for char in comp.pdf_line.pdf_character
    ]
    assert len(recorded) == len(original)
    assert all(a is b for a, b in zip(recorded, original))
    assert paragraph.first_line_indent is False


@pytest.mark.parametrize(
    "difference", ["next_line", "large_gap", "different_xobject", "render_order"]
)
def test_other_paragraph_breaks_stay_in_place(difference):
    finder = object.__new__(repair.ParagraphFinder)
    page = il.Page(pdf_paragraph=author_paragraphs(finder))
    left, dot, right = page.pdf_paragraph
    char = dot.pdf_paragraph_composition[0].pdf_line.pdf_character[0]
    if difference == "next_line":
        char.box.y -= 1
    elif difference == "large_gap":
        char.box.x += 2
    elif difference == "different_xobject":
        char.xobj_id = 1
    else:
        char.render_order += 1

    repair.restore_split_email_paragraphs(finder, page)

    assert page.pdf_paragraph == [left, dot, right]

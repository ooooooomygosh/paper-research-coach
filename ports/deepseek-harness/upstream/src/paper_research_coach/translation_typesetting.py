"""Repair a BabelDOC paragraph boundary inside a visible email address."""

from __future__ import annotations

import re

from babeldoc.format.pdf.document_il.midend.paragraph_finder import ParagraphFinder

EMAIL_START = re.compile(r"\([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]*[A-Za-z0-9]$")
EMAIL_END = re.compile(r"^[A-Za-z]{2,24}\)")


def is_adjacent(first, second):
    return (
        first.box is not None
        and second.box is not None
        and abs(first.box.y - second.box.y) <= 0.5
        and -0.25 <= second.box.x - first.box.x2 <= 1
        and first.xobj_id == second.xobj_id
        and first.render_order is not None
        and second.render_order is not None
        and first.render_order + 1 == second.render_order
    )


def restore_split_email_paragraphs(finder, page):
    paragraphs = page.pdf_paragraph
    for index in range(len(paragraphs) - 3, -1, -1):
        left, middle, right = paragraphs[index : index + 3]
        left_lines = left.pdf_paragraph_composition
        middle_lines = middle.pdf_paragraph_composition
        right_lines = right.pdf_paragraph_composition
        if (
            len(left_lines) != 1
            or len(middle_lines) != 1
            or not right_lines
            or not right.first_line_indent
            or left.layout_id is None
            or left.layout_id != right.layout_id
            or left.vertical
            or middle.vertical
            or right.vertical
            or not left_lines[0].pdf_line
            or not middle_lines[0].pdf_line
            or not right_lines[0].pdf_line
            or not EMAIL_START.search(left.unicode or "")
            or middle.unicode != "."
            or not EMAIL_END.match(right.unicode or "")
        ):
            continue
        left_chars = left_lines[0].pdf_line.pdf_character
        middle_chars = middle_lines[0].pdf_line.pdf_character
        right_chars = right_lines[0].pdf_line.pdf_character
        if not (left_chars and len(middle_chars) == 1 and right_chars):
            continue
        last, dot, first = left_chars[-1], middle_chars[0], right_chars[0]
        if not (
            dot.char_unicode == "."
            and is_adjacent(last, dot)
            and is_adjacent(dot, first)
        ):
            continue
        left.pdf_paragraph_composition = [
            finder.create_line([*left_chars, dot, *right_chars]),
            *right_lines[1:],
        ]
        finder.update_paragraph_data(left)
        left.unicode = f"{left.unicode}.{right.unicode}"
        del paragraphs[index + 1 : index + 3]


def install_split_email_repair():
    process_page = ParagraphFinder.process_page

    def process_page_with_email_repair(self, page):
        process_page(self, page)
        if not self.translation_config.ocr_workaround:
            restore_split_email_paragraphs(self, page)

    ParagraphFinder.process_page = process_page_with_email_repair

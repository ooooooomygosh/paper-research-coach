"""Reject readily detectable typesetting damage before displaying a translated PDF."""

from pathlib import Path


class TranslationLayoutError(ValueError):
    pass


def line_overlap(page, pdf):
    boxes = []
    flags = pdf.TEXTFLAGS_DICT & ~pdf.TEXT_PRESERVE_IMAGES
    for block in page.get_text("dict", flags=flags)["blocks"]:
        for line in block.get("lines", []):
            if abs(line["dir"][1]) > .08:
                continue
            box = pdf.Rect(line["bbox"])
            text = "".join(span["text"] for span in line["spans"])
            if box.height >= 4 and box.width >= 26 and sum(char.isalnum() for char in text) >= 8:
                boxes.append(box)
    boxes.sort(key=lambda box: box.y0)
    collisions = set()
    for i, first in enumerate(boxes):
        for j in range(i + 1, len(boxes)):
            second = boxes[j]
            if second.y0 >= first.y1:
                break
            overlap = first & second
            if (
                overlap.height >= .54 * max(first.height, second.height)
                and overlap.width >= max(24, .42 * min(first.width, second.width))
            ):
                collisions.update((i, j))
    return len(collisions), len(collisions) / max(1, len(boxes))


def validate_pdf_layout(source: Path, mono: Path, dual: Path) -> None:
    import pymupdf as pdf

    with pdf.open(source) as original, pdf.open(mono) as translated, pdf.open(dual) as bilingual:
        if not len(original) or len(original) != len(translated) or len(original) != len(bilingual):
            raise TranslationLayoutError("译本与原文页数不一致。请用原文阅读，或重新生成译本。")
        damaged = []
        for index, page in enumerate(translated):
            count, proportion = line_overlap(page, pdf)
            # Require sustained overlap beyond the source itself. Isolated
            # label, math or footnote collisions are not a page-wide failure.
            if count >= 8 and proportion >= .18:
                _, baseline = line_overlap(original[index], pdf)
                if proportion - baseline >= .12:
                    damaged.append(index + 1)
        if damaged:
            pages = "、".join(map(str, damaged[:8])) + (" 等" if len(damaged) > 8 else "")
            raise TranslationLayoutError(f"译本第 {pages} 页检测到大面积叠字。请用原文阅读，或重新生成译本。")

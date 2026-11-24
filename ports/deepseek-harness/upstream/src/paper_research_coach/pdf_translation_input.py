"""Keep fully clipped text out of BabelDOC's translation input."""

from __future__ import annotations

import logging
import math
import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

import pymupdf
from babeldoc.format.pdf.new_parser.tokenizer import ContentStreamTokenizer

logger = logging.getLogger(__name__)

TEXT_SHOW = {"Tj", "TJ", "'", '"'}
TEXT_OPERATORS = TEXT_SHOW | {
    "Tc",
    "Tw",
    "Tz",
    "TL",
    "Tf",
    "Ts",
    "Td",
    "TD",
    "Tm",
    "T*",
    "gs",
    "CS",
    "SC",
    "SCN",
    "G",
    "RG",
    "K",
    "cs",
    "sc",
    "scn",
    "g",
    "rg",
    "k",
}
PATH_OPERATORS = {"m", "l", "c", "v", "y", "h", "re", "W", "W*"}
PATH_END = {"S", "s", "f", "F", "f*", "B", "B*", "b", "b*", "n"}
MAX_VERIFICATION_PIXELS = 8_000_000


@dataclass(frozen=True)
class ClippedText:
    start: int
    end: int
    rectangle: bytes
    show_ends: tuple[int, ...]


def clipped_text_blocks(content: bytes) -> list[ClippedText]:
    if b"W" not in content or b"BT" not in content:
        return []
    tokenizer = ContentStreamTokenizer(content)
    operations = [
        (operation, tokenizer.pos) for operation in tokenizer.iter_operation_stream()
    ]
    operators = [operation.operator for operation, _ in operations]
    blocks = []
    open_path = in_text = False
    for i, operator in enumerate(operators):
        if (
            not open_path
            and not in_text
            and operators[i : i + 5]
            in (
                ["q", "re", "W", "n", "BT"],
                ["q", "re", "W*", "n", "BT"],
            )
        ):
            end = i + 5
            shows = []
            while end < len(operations) and operators[end] in TEXT_OPERATORS:
                if operators[end] in TEXT_SHOW:
                    shows.append(operations[end][1])
                end += 1
            # A PlacedPDF marked-content group can end between ET and Q.
            if shows and (
                operators[end : end + 2] == ["ET", "Q"]
                or operators[end : end + 3] == ["ET", "EMC", "Q"]
            ):
                rectangle = content[operations[i][1] : operations[i + 1][1]]
                blocks.append(
                    ClippedText(
                        operations[i + 3][1],
                        operations[end][1],
                        rectangle,
                        tuple(shows),
                    )
                )
        if operator in PATH_OPERATORS:
            open_path = True
        elif operator in PATH_END:
            open_path = False
        if operator in {"BT", "ET"}:
            in_text = operator == "BT"
    return blocks


def replace_content(page: pymupdf.Page, content: bytes) -> None:
    pdf = page.parent
    xref = pdf.get_new_xref()
    pdf.update_object(xref, "<<>>")
    pdf.update_stream(xref, content)
    page.set_contents(xref)


def layer_properties(page: pymupdf.Page) -> tuple[int, str]:
    pdf = page.parent
    xref, key = page.xref, ""
    for name in ("Resources", "Properties"):
        key += name
        kind, value = pdf.xref_get_key(xref, key)
        if kind == "xref":
            xref, key = int(value.split()[0]), ""
        else:
            key += "/"
    return xref, key


def fully_clipped_blocks(
    probe: pymupdf.Page, content: bytes, blocks: list[ClippedText]
) -> list[ClippedText]:
    pdf = probe.parent
    resources, properties_key = layer_properties(probe)
    layers = {}
    insertions = []
    for index, block in enumerate(blocks):
        name = f"PRCTranslationProbe{probe.number}_{index}"
        key = properties_key + name
        if pdf.xref_get_key(resources, key)[0] != "null":
            return []
        xref = pdf.add_ocg(name)
        pdf.xref_set_key(resources, key, f"{xref} 0 R")
        # The probe marks the clip with a fill in the same graphics state.
        # Marked-content boundaries flush each text run without moving it.
        marker = f"\n/OC /{name} BDC\nq\n0 g\n".encode() + block.rectangle + b" f\nQ\n"
        insertions.append((block.start, marker))
        insertions.extend((end, b"\n/Span BMC EMC\n") for end in block.show_ends)
        insertions.append((block.end, b"\nEMC\n"))
        layers[name] = block

    parts = []
    last = 0
    for offset, addition in insertions:
        parts.extend((content[last:offset], addition))
        last = offset
    parts.append(content[last:])
    replace_content(probe, b"".join(parts))
    probe = pdf.reload_page(probe)

    entries = defaultdict(list)
    for kind, bounds, layer in probe.get_bboxlog(layers=True):
        if layer in layers:
            entries[layer].append((kind, bounds))

    clipped = []
    for name, block in layers.items():
        marks = entries[name]
        if len(marks) != len(block.show_ends) + 1 or marks[0][0] != "fill-path":
            continue
        clip = pymupdf.Rect(marks[0][1])
        if clip.is_empty or not clip.is_valid or not all(map(math.isfinite, clip)):
            continue
        # Allow for floating-point rounding at the clip boundary.
        clip += (-0.25, -0.25, 0.25, 0.25)
        if all(
            kind in {"fill-text", "stroke-text"}
            and all(map(math.isfinite, bounds))
            and not pymupdf.Rect(bounds).is_empty
            and not clip.intersects(pymupdf.Rect(bounds))
            for kind, bounds in marks[1:]
        ):
            clipped.append(block)
    return clipped


def prepare_translation_input(source: Path, working_dir: Path) -> Path:
    """Return a private copy if safely clipped text can be removed."""
    try:
        with pymupdf.open(source) as pdf, pymupdf.open(source) as probe:
            if pdf.needs_pass or pdf.get_ocgs() or pdf.is_repaired:
                return source
            changed = False
            for number in range(len(pdf)):
                page = pdf[number]
                width, height = page.rect.width, page.rect.height
                if not all(
                    math.isfinite(side) and side > 0 for side in (width, height)
                ):
                    continue
                if math.ceil(width) * math.ceil(height) > MAX_VERIFICATION_PIXELS:
                    continue
                content = b"\n".join(
                    pdf.xref_stream(xref) for xref in page.get_contents()
                )
                candidates = clipped_text_blocks(content)
                if not candidates:
                    continue
                clipped = fully_clipped_blocks(probe[number], content, candidates)
                if not clipped:
                    continue
                normalized = content
                for block in reversed(clipped):
                    normalized = (
                        normalized[: block.start] + b"\n" + normalized[block.end :]
                    )
                before = page.get_pixmap(alpha=True, annots=False)
                original_contents = pdf.xref_get_key(page.xref, "Contents")[1]
                replace_content(page, normalized)
                page = pdf.reload_page(page)
                after = page.get_pixmap(alpha=True, annots=False)
                if before.samples_mv != after.samples_mv:
                    pdf.xref_set_key(page.xref, "Contents", original_contents)
                    continue
                changed = True
            if not changed:
                return source

            target_dir = working_dir / "visible-source"
            target = target_dir / source.name
            if target.resolve() == source.resolve():
                return source
            target_dir.mkdir(parents=True, exist_ok=True)
            with TemporaryDirectory(dir=target_dir) as tmp:
                staged = Path(tmp) / "input.pdf"
                pdf.save(staged, garbage=1)
                os.replace(staged, target)
            return target
    except Exception:
        logger.warning(
            "Could not verify clipped translation text; using original PDF",
            exc_info=True,
        )
        return source

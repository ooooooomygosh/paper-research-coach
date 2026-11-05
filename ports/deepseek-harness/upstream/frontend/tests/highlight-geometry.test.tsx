import { afterEach, describe, expect, it, vi } from "vitest";
import { mergeHighlightRects, selectedTextRects, selectionPopoverPosition } from "../src/highlightGeometry";

afterEach(() => { vi.restoreAllMocks(); document.body.replaceChildren(); });

describe("PDF text highlight geometry", () => {
  it("paints duplicate, contained and overlapping Chinese glyph fragments once per line", () => {
    const rects = [[100, 700, 110, 710], [100, 700, 110, 710], [102, 701, 108, 709],
      [108, 700, 120, 710], [120.2, 700, 130, 710], [100, 682, 150, 692]];
    expect(mergeHighlightRects(rects)).toEqual([[100, 700, 130, 710], [100, 682, 150, 692]]);
    expect(rects[0]).toEqual([100, 700, 110, 710]);
  });

  it("keeps separate lines and the whitespace between columns unpainted", () => {
    expect(mergeHighlightRects([[10, 100, 100, 110], [10, 115, 100, 125], [180, 100, 260, 110]]))
      .toEqual([[10, 115, 100, 125], [10, 100, 100, 110], [180, 100, 260, 110]]);
  });

  it("normalizes reversed corners and ignores malformed or empty boxes", () => {
    expect(mergeHighlightRects([[40, 20, 10, 10], [NaN, 0, 1, 1], [0, 0, 0, 12], [1, 2, 3]]))
      .toEqual([[10, 10, 40, 20]]);
  });

  it("reads only selected text subranges, excluding Chromium's enclosing span boxes", () => {
    const layer = document.createElement("div");
    layer.innerHTML = "<span>模型并不满足</span><span>混凝土应力应变</span>";
    document.body.append(layer);
    const first = layer.children[0].firstChild!, second = layer.children[1].firstChild!;
    const range = document.createRange();
    range.setStart(first, 2); range.setEnd(second, 3);
    Object.defineProperty(range, "getClientRects", { value: () => { throw new Error("Parent element boxes must not be used"); } });
    const calls: [Node, number, number][] = [];
    const old = Object.getOwnPropertyDescriptor(Range.prototype, "getClientRects");
    Object.defineProperty(Range.prototype, "getClientRects", { configurable: true, value: function(this: Range) {
      calls.push([this.startContainer, this.startOffset, this.endOffset]);
      return [{ left: 10, top: 20, right: 50, bottom: 32, width: 40, height: 12 }];
    } });
    try {
      expect(selectedTextRects(range, layer)).toHaveLength(2);
      expect(calls).toEqual([[first, 2, 6], [second, 0, 3]]);
    } finally {
      if (old) Object.defineProperty(Range.prototype, "getClientRects", old);
      else delete (Range.prototype as any).getClientRects;
    }
  });
});

describe("selection popover placement", () => {
  it("moves above a selection near the bottom instead of clamping over the text", () => {
    const position = selectionPopoverPosition({ left: 200, right: 700, top: 610, bottom: 650 }, 200, 660, 340, 280, 1200, 800);
    expect(position).toEqual({ left: 200, top: 320 });
    expect(position.top + 280).toBeLessThan(610);
  });

  it("uses space alongside a tall selection when neither above nor below fits", () => {
    const position = selectionPopoverPosition({ left: 50, right: 650, top: 30, bottom: 760 }, 50, 770, 340, 300, 1200, 800);
    expect(position).toEqual({ left: 660, top: 30 });
  });

  it("uses the measured dimensions and keeps the popover within the viewport", () => {
    const p = selectionPopoverPosition(undefined, 950, 750, 340, 410, 1024, 768);
    expect(p).toEqual({ left: 672, top: 346 });
    expect(p.top + 410).toBeLessThanOrEqual(768 - 12);
  });
});

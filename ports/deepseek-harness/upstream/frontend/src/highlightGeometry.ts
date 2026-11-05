export type Rect = [number, number, number, number];
export type Bounds = { left: number; top: number; right: number; bottom: number };

/** Chromium's whole-range rectangles include both element boxes and text boxes.
 * Walk only the selected text fragments so parent spans cannot paint twice. */
export function selectedTextRects(range: Range, layer: HTMLElement): Bounds[] {
  const walker = layer.ownerDocument.createTreeWalker(layer, NodeFilter.SHOW_TEXT);
  const rects: Bounds[] = [];
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    if (!range.intersectsNode(node) || !node.textContent?.length) continue;
    const from = node === range.startContainer ? range.startOffset : 0;
    const to = node === range.endContainer ? range.endOffset : node.textContent.length;
    if (from >= to) continue;
    const fragment = layer.ownerDocument.createRange();
    fragment.setStart(node, from);
    fragment.setEnd(node, to);
    for (const rect of fragment.getClientRects()) {
      if (rect.width > 0.5 && rect.height > 0.5)
        rects.push({ left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom });
    }
  }
  return rects;
}

/** One band per connected part of a text line. Keep columns and line gaps apart.
 * Also applies at draw time, so old notes with duplicated geometry render cleanly. */
export function mergeHighlightRects(input: readonly number[][]): Rect[] {
  const rects: Rect[] = input.flatMap((r) => {
    if (r.length !== 4 || !r.every(Number.isFinite)) return [];
    const box: Rect = [Math.min(r[0], r[2]), Math.min(r[1], r[3]), Math.max(r[0], r[2]), Math.max(r[1], r[3])];
    return box[2] - box[0] > 0.01 && box[3] - box[1] > 0.01 ? [box] : [];
  }).sort((a, b) => (b[1] + b[3]) - (a[1] + a[3]) || a[0] - b[0]);
  const rows: { center: number; height: number; rects: Rect[] }[] = [];
  for (const rect of rects) {
    const height = rect[3] - rect[1], center = (rect[1] + rect[3]) / 2;
    const row = rows.find((line) => {
      const overlap = Math.min(line.center + line.height / 2, rect[3]) - Math.max(line.center - line.height / 2, rect[1]);
      return overlap >= Math.min(line.height, height) * 0.65 &&
        Math.abs(center - line.center) <= Math.max(height, line.height) * 0.4 &&
        Math.min(height, line.height) >= Math.max(height, line.height) * 0.45;
    });
    if (row) row.rects.push(rect);
    else rows.push({ center, height, rects: [rect] });
  }
  return rows.flatMap((row) => {
    const merged: Rect[] = [];
    for (const rect of row.rects.sort((a, b) => a[0] - b[0] || b[2] - a[2])) {
      const previous = merged.at(-1);
      const gap = Math.min(2, row.height * 0.2);
      if (previous && rect[0] <= previous[2] + gap) {
        previous[1] = Math.min(previous[1], rect[1]);
        previous[2] = Math.max(previous[2], rect[2]);
        previous[3] = Math.max(previous[3], rect[3]);
      } else merged.push([...rect]);
    }
    return merged;
  });
}

/** Use actual popover dimensions, preferring space outside the selected lines. */
export function selectionPopoverPosition(bounds: Bounds | undefined, x: number, y: number,
  width: number, height: number, viewportWidth: number, viewportHeight: number) {
  const margin = 12, gap = 10;
  const maxX = Math.max(margin, viewportWidth - width - margin);
  const maxY = Math.max(margin, viewportHeight - height - margin);
  const clamp = (left: number, top: number) => ({ left: Math.max(margin, Math.min(left, maxX)), top: Math.max(margin, Math.min(top, maxY)) });
  if (!bounds) return clamp(x, y);
  const candidates = [clamp(bounds.left, bounds.bottom + gap), clamp(bounds.left, bounds.top - height - gap),
    clamp(bounds.right + gap, bounds.top), clamp(bounds.left - width - gap, bounds.top),
    clamp(maxX, maxY), clamp(margin, margin)];
  const overlap = (p: { left: number; top: number }) =>
    Math.max(0, Math.min(p.left + width, bounds.right) - Math.max(p.left, bounds.left)) *
    Math.max(0, Math.min(p.top + height, bounds.bottom) - Math.max(p.top, bounds.top));
  return candidates.reduce((best, candidate) => overlap(candidate) < overlap(best) ? candidate : best);
}

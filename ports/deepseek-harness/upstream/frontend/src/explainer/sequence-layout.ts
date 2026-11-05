import type { SequenceBlock } from "./types";
import { plain, textWidth, wrapText } from "./measure";

const FS = 13;
const LH = 16;
const ACTOR_H = 34;
const TOP = 8;

export type SeqLayout = {
  width: number;
  height: number;
  col: number;
  actors: { name: string; x: number; w: number }[];
  items: (
    | { kind: "msg"; n: number | null; x1: number; x2: number; y: number; dashed: boolean; lines: string[]; self: boolean }
    | { kind: "note"; x: number; w: number; y: number; h: number; lines: string[] }
    | { kind: "divider"; y: number; text: string }
  )[];
  lifelineTop: number;
  lifelineBottom: number;
};

export function layoutSequence(block: SequenceBlock): SeqLayout {
  const labels = block.steps.map((s) => (s.kind === "msg" ? plain(s.label) : ""));
  const widest = Math.max(0, ...labels.map((l) => textWidth(l, FS)));
  const col = Math.min(260, Math.max(130, Math.ceil(widest) / 1.15 + 36));
  const index = new Map(block.participants.map((p, i) => [p, i]));
  const cx = (name: string) => col / 2 + 8 + (index.get(name) ?? 0) * col;
  const actors = block.participants.map((name) => ({
    name,
    x: cx(name),
    w: Math.min(col - 12, Math.max(70, Math.ceil(textWidth(name, FS)) + 24)),
  }));
  let y = TOP + ACTOR_H + 22;
  let n = 0;
  const items: SeqLayout["items"] = [];
  for (const step of block.steps) {
    if (step.kind === "msg") {
      const lines = wrapText(plain(step.label), FS, Math.max(90, col - 20));
      const self = step.from === step.to;
      const labelH = lines.length * LH;
      y += step.label ? labelH + 4 : 6;
      items.push({
        kind: "msg",
        n: block.numbered ? ++n : null,
        x1: cx(step.from),
        x2: self ? cx(step.from) + 34 : cx(step.to),
        y,
        dashed: step.dashed,
        lines: step.label ? lines : [],
        self,
      });
      y += self ? 26 : 16;
    } else if (step.kind === "note") {
      const xs = step.over.map(cx);
      const lo = Math.min(...xs) - 54;
      const hi = Math.max(...xs) + 54;
      const lines = wrapText(plain(step.text), FS, hi - lo - 20);
      const h = lines.length * LH + 12;
      items.push({ kind: "note", x: lo, w: hi - lo, y, h, lines });
      y += h + 14;
    } else {
      y += 6;
      items.push({ kind: "divider", y: y + 6, text: step.text });
      y += 24;
    }
  }
  return {
    width: Math.ceil(block.participants.length * col + 16 + 40),
    height: y + 12,
    col,
    actors,
    items,
    lifelineTop: TOP + ACTOR_H,
    lifelineBottom: y,
  };
}

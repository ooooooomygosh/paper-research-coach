import dagre from "@dagrejs/dagre";
import type { FlowBlock } from "./types";
import { plain, textWidth, wrapText } from "./measure";

const FS = 13;
const LH = 17;
const MAX_TEXT = 150;
const EDGE_FS = 11.5;

export type Placed = {
  id: string;
  lines: string[];
  shape: "rect" | "round" | "diamond" | "db";
  hi: boolean;
  x: number;
  y: number;
  w: number;
  h: number;
};
export type PlacedEdge = {
  d: string;
  dashed: boolean;
  label: string;
  lx: number;
  ly: number;
  lw: number;
};
export type FlowLayout = {
  width: number;
  height: number;
  nodes: Placed[];
  edges: PlacedEdge[];
  groups: { name: string; x: number; y: number; w: number; h: number }[];
};

function size(label: string, shape: Placed["shape"]) {
  const lines = wrapText(plain(label), FS, MAX_TEXT);
  const text = Math.max(...lines.map((l) => textWidth(l, FS)));
  const w = Math.max(54, Math.ceil(text) + (shape === "diamond" ? 52 : 28));
  const h = lines.length * LH + (shape === "diamond" ? 30 : shape === "db" ? 24 : 16);
  return { lines, w, h };
}

export function layoutFlow(block: FlowBlock): FlowLayout {
  const g = new dagre.graphlib.Graph({ compound: true, multigraph: true });
  g.setGraph({ rankdir: block.dir, nodesep: 26, ranksep: 46, marginx: 10, marginy: 10 });
  g.setDefaultEdgeLabel(() => ({}));
  const info = new Map<string, ReturnType<typeof size>>();
  for (const n of block.nodes) {
    const s = size(n.label, n.shape);
    info.set(n.id, s);
    g.setNode(n.id, { width: s.w, height: s.h });
  }
  block.groups.forEach((grp, i) => {
    const id = `\u0000group${i}`;
    g.setNode(id, { label: grp.name });
    for (const m of grp.members) g.setParent(m, id);
  });
  block.edges.forEach((e, i) => {
    const label = plain(e.label);
    g.setEdge(e.from, e.to, label
      ? { width: Math.ceil(textWidth(label, EDGE_FS)) + 10, height: 16, labelpos: "c" }
      : {}, String(i));
  });
  dagre.layout(g);

  const nodes: Placed[] = block.nodes.map((n) => {
    const p = g.node(n.id);
    const s = info.get(n.id)!;
    return { id: n.id, lines: s.lines, shape: n.shape, hi: n.hi, x: p.x - s.w / 2, y: p.y - s.h / 2, w: s.w, h: s.h };
  });
  const edges: PlacedEdge[] = block.edges.map((e, i) => {
    const p = g.edge({ v: e.from, w: e.to, name: String(i) });
    const pts: { x: number; y: number }[] = p.points ?? [];
    const label = plain(e.label);
    return {
      d: pts.map((q, k) => `${k ? "L" : "M"}${q.x.toFixed(1)} ${q.y.toFixed(1)}`).join(" "),
      dashed: e.dashed,
      label,
      lx: p.x ?? pts[Math.floor(pts.length / 2)]?.x ?? 0,
      ly: p.y ?? pts[Math.floor(pts.length / 2)]?.y ?? 0,
      lw: label ? Math.ceil(textWidth(label, EDGE_FS)) + 10 : 0,
    };
  });
  const groups = block.groups.map((grp, i) => {
    const p = g.node(`\u0000group${i}`);
    return { name: grp.name, x: p.x - p.width / 2, y: p.y - p.height / 2, w: p.width, h: p.height };
  });
  const graph = g.graph();
  return { width: Math.ceil(graph.width ?? 0), height: Math.ceil(graph.height ?? 0), nodes, edges, groups };
}

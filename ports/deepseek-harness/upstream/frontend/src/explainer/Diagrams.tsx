import { useMemo } from "react";
import type { FlowBlock, KvBlock, SequenceBlock, TimelineBlock, TreeBlock, TreeNode } from "./types";
import { layoutFlow } from "./flow-layout";
import { layoutSequence } from "./sequence-layout";
import { Inline } from "./Inline";

const FS = 13;
const LH = 17;

function Defs({ id }: { id: string }) {
  return (
    <defs>
      <marker id={id} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M0 0 L10 5 L0 10 z" className="xp-arrowhead" />
      </marker>
    </defs>
  );
}

function Lines({ lines, x, y, anchor = "middle" }: { lines: string[]; x: number; y: number; anchor?: "middle" | "start" }) {
  const top = y - ((lines.length - 1) * LH) / 2;
  return (
    <>
      {lines.map((line, i) => (
        <text key={i} x={x} y={top + i * LH} textAnchor={anchor} dominantBaseline="central" fontSize={FS}>
          {line}
        </text>
      ))}
    </>
  );
}

export function FlowDiagram({ block, uid }: { block: FlowBlock; uid: string }) {
  const layout = useMemo(() => layoutFlow(block), [block]);
  const marker = `xp-arrow-${uid}`;
  return (
    <div className="xp-diagram" role="img" aria-label={"流程图：" + block.nodes.map((n) => n.label).join("、")}>
      <svg viewBox={`0 0 ${layout.width} ${layout.height}`} style={{ width: "100%", maxWidth: layout.width, minWidth: Math.min(layout.width, 460) }}>
        <Defs id={marker} />
        {layout.groups.map((g) => (
          <g key={g.name}>
            <rect x={g.x} y={g.y} width={g.w} height={g.h} rx={8} className="xp-group" />
            <text x={g.x + 8} y={g.y + 12} fontSize={11} className="xp-group-label">
              {g.name}
            </text>
          </g>
        ))}
        {layout.edges.map((e, i) => (
          <g key={i}>
            <path d={e.d} className={"xp-edge" + (e.dashed ? " dashed" : "")} markerEnd={`url(#${marker})`} fill="none" />
            {e.label && (
              <g>
                <rect x={e.lx - e.lw / 2} y={e.ly - 9} width={e.lw} height={18} rx={4} className="xp-edge-bg" />
                <text x={e.lx} y={e.ly} textAnchor="middle" dominantBaseline="central" fontSize={11.5} className="xp-edge-label">
                  {e.label}
                </text>
              </g>
            )}
          </g>
        ))}
        {layout.nodes.map((n) => {
          const cx = n.x + n.w / 2;
          const cy = n.y + n.h / 2;
          const cls = "xp-node" + (n.hi ? " hi" : "");
          return (
            <g key={n.id} className={cls}>
              {n.shape === "diamond" ? (
                <polygon points={`${cx},${n.y} ${n.x + n.w},${cy} ${cx},${n.y + n.h} ${n.x},${cy}`} />
              ) : n.shape === "db" ? (
                <>
                  <path d={`M${n.x} ${n.y + 8} v${n.h - 16} a${n.w / 2} 8 0 0 0 ${n.w} 0 v${-(n.h - 16)} a${n.w / 2} 8 0 0 0 ${-n.w} 0 z`} />
                  <path d={`M${n.x} ${n.y + 8} a${n.w / 2} 8 0 0 0 ${n.w} 0`} fill="none" />
                </>
              ) : (
                <rect x={n.x} y={n.y} width={n.w} height={n.h} rx={n.shape === "round" ? n.h / 2 : 6} />
              )}
              <Lines lines={n.lines} x={cx} y={cy} />
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export function SequenceDiagram({ block, uid }: { block: SequenceBlock; uid: string }) {
  const L = useMemo(() => layoutSequence(block), [block]);
  const marker = `xp-seq-${uid}`;
  return (
    <div className="xp-diagram" role="img" aria-label={"时序图：" + block.participants.join("、")}>
      <svg viewBox={`0 0 ${L.width} ${L.height}`} style={{ width: "100%", maxWidth: L.width, minWidth: Math.min(L.width, 460) }}>
        <Defs id={marker} />
        {L.actors.map((a) => (
          <g key={a.name}>
            <line x1={a.x} x2={a.x} y1={L.lifelineTop} y2={L.lifelineBottom} className="xp-lifeline" />
            <g className="xp-node">
              <rect x={a.x - a.w / 2} y={8} width={a.w} height={34} rx={6} />
              <text x={a.x} y={25} textAnchor="middle" dominantBaseline="central" fontSize={FS}>
                {a.name}
              </text>
            </g>
          </g>
        ))}
        {L.items.map((it, i) =>
          it.kind === "msg" ? (
            <g key={i}>
              {it.self ? (
                <path d={`M${it.x1} ${it.y - 6} h${34} v14 h${-34}`} className={"xp-edge" + (it.dashed ? " dashed" : "")} fill="none" markerEnd={`url(#${marker})`} />
              ) : (
                <line x1={it.x1} x2={it.x2} y1={it.y} y2={it.y} className={"xp-edge" + (it.dashed ? " dashed" : "")} markerEnd={`url(#${marker})`} />
              )}
              {it.lines.map((line, k) => (
                <text
                  key={k}
                  x={it.self ? it.x1 + 40 : (it.x1 + it.x2) / 2}
                  y={it.y - 8 - (it.lines.length - 1 - k) * 16}
                  textAnchor={it.self ? "start" : "middle"}
                  fontSize={FS}
                  className="xp-edge-label"
                >
                  {(it.n && k === 0 ? `${it.n}. ` : "") + line}
                </text>
              ))}
            </g>
          ) : it.kind === "note" ? (
            <g key={i} className="xp-note">
              <rect x={it.x} y={it.y} width={it.w} height={it.h} rx={4} />
              <Lines lines={it.lines} x={it.x + it.w / 2} y={it.y + it.h / 2} />
            </g>
          ) : (
            <g key={i}>
              <line x1={8} x2={L.width - 8} y1={it.y} y2={it.y} className="xp-divider" />
              <text x={L.width / 2} y={it.y} textAnchor="middle" dominantBaseline="central" fontSize={11.5} className="xp-divider-label">
                {" " + it.text + " "}
              </text>
            </g>
          ),
        )}
      </svg>
    </div>
  );
}

function TreeItems({ nodes }: { nodes: TreeNode[] }) {
  return (
    <ul>
      {nodes.map((n, i) => (
        <li key={i} className={n.hi ? "hi" : ""}>
          <span className="xp-tree-label">
            <Inline text={n.label} />
          </span>
          {n.note && (
            <span className="xp-tree-note">
              <Inline text={n.note} />
            </span>
          )}
          {n.children.length > 0 && <TreeItems nodes={n.children} />}
        </li>
      ))}
    </ul>
  );
}

export function TreeView({ block }: { block: TreeBlock }) {
  return (
    <div className="xp-tree">
      <TreeItems nodes={block.roots} />
    </div>
  );
}

export function TimelineView({ block }: { block: TimelineBlock }) {
  return (
    <ol className={"xp-timeline" + (block.vertical ? " vertical" : "")}>
      {block.items.map((it, i) => (
        <li key={i} className={it.hi ? "hi" : ""}>
          <span className="xp-when">{it.when}</span>
          <span className="xp-dot" aria-hidden="true" />
          <span className="xp-title">
            <Inline text={it.title} />
          </span>
          {it.detail && (
            <span className="xp-detail">
              <Inline text={it.detail} />
            </span>
          )}
        </li>
      ))}
    </ol>
  );
}

export function KvView({ block }: { block: KvBlock }) {
  return (
    <dl className="xp-kv" style={{ gridTemplateColumns: `repeat(${block.cols}, minmax(0, 1fr))` }}>
      {block.cells.map((c, i) => (
        <div key={i} className={c.wide ? "wide" : ""} style={c.wide ? { gridColumn: "1 / -1" } : undefined}>
          <dt>{c.key}</dt>
          <dd>
            <Inline text={c.value} />
          </dd>
        </div>
      ))}
    </dl>
  );
}

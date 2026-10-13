import { useEffect, useId, useMemo, useRef, useState } from "react";
import { HelpCircle, MessageCircle } from "lucide-react";
import type { AskBlock, Block, ExplainerDoc } from "./types";
import { FlowDiagram, KvView, SequenceDiagram, TimelineView, TreeView } from "./Diagrams";
import { Inline, Prose } from "./Inline";

function Ask({ block, onAnswer, disabled }: { block: AskBlock; onAnswer?: (text: string) => void; disabled?: boolean }) {
  const name = useId();
  const [picked, setPicked] = useState<Set<number>>(
    () => new Set(block.options.flatMap((o, i) => (o.suggested ? [i] : []))),
  );
  const toggle = (i: number) =>
    setPicked((prev) => {
      const next = new Set(block.multi ? prev : []);
      if (block.multi && prev.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  const answer = [...picked].sort().map((i) => block.options[i].label).join("；");
  return (
    <fieldset className="xp-ask">
      <legend>
        <Inline text={block.question} />
      </legend>
      {block.options.map((o, i) => (
        <label key={i} className={picked.has(i) ? "on" : ""}>
          <input
            type={block.multi ? "checkbox" : "radio"}
            name={name}
            checked={picked.has(i)}
            onChange={() => toggle(i)}
          />
          <span>
            <b>
              <Inline text={o.label} />
            </b>
            {o.suggested && <em>建议</em>}
            {o.note && (
              <small>
                <Inline text={o.note} />
              </small>
            )}
          </span>
        </label>
      ))}
      {onAnswer && (
        <button
          type="button"
          className="xp-ask-send"
          disabled={disabled || !picked.size}
          onClick={() => onAnswer(`我的选择：${block.question} → ${answer}`)}
        >
          按这个选择继续
        </button>
      )}
    </fieldset>
  );
}

function BlockView({ block, uid, onAnswer, disabled, narrow = false }: { block: Block; uid: string; onAnswer?: (t: string) => void; disabled?: boolean; narrow?: boolean }) {
  // A long left-to-right flow does not fit a narrow column: draw it top to bottom there.
  const flow = useMemo(
    () => (block.type === "flow" && narrow && (block.dir === "LR" || block.dir === "RL") && block.nodes.length > 3 ? { ...block, dir: "TB" as const } : block),
    [block, narrow],
  );
  if (flow !== block) return <FlowDiagram block={flow as typeof block & { type: "flow" }} uid={uid} />;
  switch (block.type) {
    case "md":
      return <Prose text={block.text} />;
    case "flow":
      return <FlowDiagram block={block} uid={uid} />;
    case "sequence":
      return <SequenceDiagram block={block} uid={uid} />;
    case "tree":
      return <TreeView block={block} />;
    case "timeline":
      return <TimelineView block={block} />;
    case "kv":
      return <KvView block={block} />;
    case "callout":
      return (
        <div className={"xp-callout " + block.kind} role="note">
          {block.title && <strong>{block.title}</strong>}
          {block.text && <Prose text={block.text} />}
        </div>
      );
    case "ask":
      return <Ask block={block} onAnswer={onAnswer} disabled={disabled} />;
    default:
      return null;
  }
}

const LETTERS = "ABCDEFGHIJKLMNOP";
export const panelLetter = (i: number) => LETTERS[i] || String(i + 1);

/** A panel that reads best at full width: a left-to-right flow, a wide table, a sequence or a timeline. */
function wide(blocks: Block[]) {
  return blocks.some((b) =>
    (b.type === "flow" && (b.dir === "LR" || b.dir === "RL") && b.nodes.length > 3) ||
    b.type === "sequence" ||
    (b.type === "timeline" && !b.vertical) ||
    (b.type === "md" && /^\s*\|.*\|.*\|.*\|.*\|/m.test(b.text)),
  );
}
const diagram = (blocks: Block[]) => blocks.some((b) => b.type === "flow" || b.type === "sequence");

export type PanelAsk = (letter: string, title: string, kind: "ask" | "confused") => void;

/**
 * One explainer page in the Answer-me-with-HTML layout: the conclusion first, then lettered
 * panel cards in a grid (two columns when there is room). Everything is drawn from typed data.
 */
export function ExplainerView({
  doc,
  onAnswer,
  disabled,
  onPanelAsk,
  compact = false,
}: {
  doc: ExplainerDoc;
  onAnswer?: (text: string) => void;
  disabled?: boolean;
  /** Per-panel follow-ups: "ask about this panel" and "I did not get this panel". */
  onPanelAsk?: PanelAsk;
  /** One column, smaller type: a figure inside a chat reply. */
  compact?: boolean;
}) {
  const uid = useId().replace(/:/g, "");
  const root = useRef<HTMLElement>(null);
  const [narrow, setNarrow] = useState(compact);
  useEffect(() => {
    const el = root.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => setNarrow(compact || entry.contentRect.width < 560));
    observer.observe(el);
    return () => observer.disconnect();
  }, [compact]);
  // The tag already says "conclusion"; drop the same words at the start of the text.
  const lead = doc.lead.map((b, i) =>
    i === 0 && b.type === "md" ? { ...b, text: b.text.replace(/^\s*(先说结论|结论|简单说|一句话|short answer|in short|answer)\s*[:：]\s*/i, "") } : b,
  );
  return (
    <article ref={root} className={"xp-doc" + (compact ? " compact" : "")} lang={doc.lang === "zh" ? "zh-CN" : doc.lang}>
      {doc.subtitle && <p className="xp-subtitle">{doc.subtitle}</p>}
      {doc.lead.length > 0 && (
        <div className="xp-lead" role="note" aria-label={doc.lang === "en" ? "Short answer" : "结论"}>
          <span className="xp-lead-tag" aria-hidden="true">{doc.lang === "en" ? "Answer" : "结论"}</span>
          {lead.map((b, i) => (
            <BlockView key={i} block={b} uid={`${uid}l${i}`} onAnswer={onAnswer} disabled={disabled} narrow={narrow} />
          ))}
        </div>
      )}
      <div className="xp-grid">
        {doc.panels.map((p, i) => {
          const letter = panelLetter(i);
          const full = (p.span ?? 1) >= 2 || wide(p.blocks);
          return (
            <section
              key={i}
              className={"xp-section" + (full ? " span-2" : "") + (diagram(p.blocks) ? " has-diagram" : "") + (p.bare ? " bare" : "")}
              aria-label={`${letter} ${p.title}`}
            >
              {!p.bare && (
                <header className="xp-panel-head">
                  <span className="xp-letter" aria-hidden="true">{letter}</span>
                  <h3>{p.title}</h3>
                  {p.meta && <small className="xp-meta">{p.meta}</small>}
                  {onPanelAsk && (
                    <span className="xp-panel-actions" data-export="skip">
                      <button type="button" title="追问这一块" aria-label={`追问 ${letter}「${p.title}」`} disabled={disabled}
                        onClick={() => onPanelAsk(letter, p.title, "ask")}>
                        <MessageCircle size={13} />
                      </button>
                      <button type="button" title="这一块没看懂" aria-label={`${letter}「${p.title}」没看懂`} disabled={disabled}
                        onClick={() => onPanelAsk(letter, p.title, "confused")}>
                        <HelpCircle size={13} />
                      </button>
                    </span>
                  )}
                </header>
              )}
              <div className="xp-panel-body">
                {p.blocks.map((b, k) => (
                  <BlockView key={k} block={b} uid={`${uid}p${i}b${k}`} onAnswer={onAnswer} disabled={disabled} narrow={narrow} />
                ))}
              </div>
            </section>
          );
        })}
      </div>
    </article>
  );
}

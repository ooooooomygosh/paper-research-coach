import { useId, useState } from "react";
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

function BlockView({ block, uid, onAnswer, disabled }: { block: Block; uid: string; onAnswer?: (t: string) => void; disabled?: boolean }) {
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

export function ExplainerView({
  doc,
  onAnswer,
  disabled,
}: {
  doc: ExplainerDoc;
  onAnswer?: (text: string) => void;
  disabled?: boolean;
}) {
  const uid = useId().replace(/:/g, "");
  return (
    <article className="xp-doc" lang={doc.lang === "zh" ? "zh-CN" : doc.lang}>
      {doc.subtitle && <p className="xp-subtitle">{doc.subtitle}</p>}
      {doc.lead.length > 0 && (
        <div className="xp-lead">
          {doc.lead.map((b, i) => (
            <BlockView key={i} block={b} uid={`${uid}l${i}`} onAnswer={onAnswer} disabled={disabled} />
          ))}
        </div>
      )}
      {doc.panels.map((p, i) => (
        <section key={i} className="xp-section">
          <h3>{p.title}</h3>
          {p.blocks.map((b, k) => (
            <BlockView key={k} block={b} uid={`${uid}p${i}b${k}`} onAnswer={onAnswer} disabled={disabled} />
          ))}
        </section>
      ))}
    </article>
  );
}

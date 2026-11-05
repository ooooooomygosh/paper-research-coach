import { useEffect, useState } from "react";
import { ChevronDown, ChevronUp, ExternalLink } from "lucide-react";
import { api } from "../api";
import { ExplainerView } from "./ExplainerDoc";
import type { ExplainerRecord } from "./types";
import "./explainer.css";

/** A small diagram inside a mainline reply. It is part of the reply, not a detour. */
export default function MainlineFigure({ id, rev, onAnswer, disabled, onOpen }: {
  id: string;
  rev?: string;
  onAnswer?: (text: string) => void;
  disabled?: boolean;
  onOpen?: () => void;
}) {
  const [record, setRecord] = useState<ExplainerRecord | null>(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);
  // A figure that asks the reader to choose starts open, so the choice is never hidden.
  useEffect(() => {
    if (record && [...record.doc.lead, ...record.doc.panels.flatMap((p) => p.blocks)].some((b) => b.type === "ask")) setOpen(true);
  }, [record?.id]);
  useEffect(() => {
    let live = true;
    api("coach/explainer/" + id)
      .then((r) => live && (setRecord(r), setError("")))
      .catch((e) => live && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      live = false;
    };
  }, [id, rev]);
  if (!record) return error ? <p className="xp-inline-error" role="alert">图解没有加载：{error}</p> : null;
  return (
    <figure className={"xp-inline" + (open ? " open" : "")} aria-label={"图解：" + record.title}>
      <figcaption>
        <b>{record.title}</b>
        <span>
          <button type="button" className="text-button" aria-expanded={open} onClick={() => setOpen(!open)}>
            {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
            {open ? "收起" : "展开全部"}
          </button>
          {onOpen && (
            <button type="button" className="text-button" title="在新窗口打开" aria-label="在新窗口打开图解" onClick={onOpen}>
              <ExternalLink size={13} />
            </button>
          )}
        </span>
      </figcaption>
      <div className="xp-inline-body">
        <ExplainerView doc={record.doc} onAnswer={onAnswer} disabled={disabled} compact />
      </div>
    </figure>
  );
}

import { useEffect, useRef, useState } from "react";
import { ArrowUp, ChevronDown, ChevronUp, Download, ExternalLink, Maximize2, Sparkles } from "lucide-react";
import { api } from "../api";
import { ExplainerView, type PanelAsk } from "./ExplainerDoc";
import { downloadHtml, explainerHtml } from "./exportHtml";
import type { ExplainerRecord } from "./types";
import "./explainer.css";

export type Quest = { status?: "open" | "done" | "parked"; takeaway?: string };

/** The first sentence of the conclusion, as plain text for the collapsed card. */
function gist(record: ExplainerRecord) {
  const lead = record.doc.lead.find((b) => b.type === "md") as { text: string } | undefined;
  const text = (lead?.text || record.doc.subtitle || "").replace(/[*_`#>$\\]/g, "").replace(/\s+/g, " ").trim();
  return text.length > 90 ? text.slice(0, 88) + "…" : text;
}

/**
 * A side quest's explainer page, inside the conversation. Collapsed it is one line (title and
 * conclusion); expanded it is the whole interactive page: diagrams, tables, formulas, decisions,
 * per-panel follow-ups and a box to ask the next question in the same branch.
 */
export default function ExplainerCard({
  id,
  rev,
  branchId,
  expanded,
  onToggle,
  disabled,
  onAsk,
  onEnlarge,
  onPopout,
  paperTitle = "",
  quest,
  questSlot,
}: {
  id: string;
  rev?: string;
  branchId: string;
  expanded: boolean;
  onToggle: (open: boolean) => void;
  disabled?: boolean;
  /** Send a follow-up in this branch (a detour that keeps the mainline where it is). */
  onAsk: (text: string, branchId: string) => void;
  onEnlarge?: () => void;
  onPopout?: () => void;
  paperTitle?: string;
  quest?: Quest;
  /** The side-quest controls ("I get it now"), drawn under the page. */
  questSlot?: React.ReactNode;
}) {
  const [record, setRecord] = useState<ExplainerRecord | null>(null);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState("");
  const page = useRef<HTMLDivElement>(null);
  const box = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    let live = true;
    api("coach/explainer/" + id)
      .then((r) => live && (setRecord(r), setError("")))
      .catch((e) => live && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      live = false;
    };
  }, [id, rev]);

  const ask = (text: string) => {
    if (!text.trim() || disabled) return;
    onAsk(text.trim(), branchId);
    setDraft("");
  };
  const panelAsk: PanelAsk = (letter, title, kind) => {
    if (kind === "confused") ask(`${letter}「${title}」这一块我没看懂，请换个说法，或者举一个小例子。`);
    else {
      setDraft(`关于 ${letter}「${title}」：`);
      requestAnimationFrame(() => {
        box.current?.focus();
        box.current?.setSelectionRange(box.current.value.length, box.current.value.length);
      });
    }
  };
  const done = quest?.status === "done";

  return (
    <section className={"xp-card" + (expanded ? " open" : "") + (done ? " done" : "")} aria-label={"讲解页：" + (record?.title || "")}>
      <header className="xp-card-head">
        <button type="button" className="xp-card-toggle" aria-expanded={expanded} onClick={() => onToggle(!expanded)}>
          <span className="xp-card-kind"><Sparkles size={12} />支线{record && record.seq > 1 ? ` · 第 ${record.seq} 页` : ""}</span>
          <b>{record?.title || (error ? "讲解页没有加载" : "正在打开讲解页…")}</b>
          {record && !expanded && <span className="xp-card-gist">{gist(record)}</span>}
          {done && <span className="xp-card-status">已弄懂</span>}
          {quest?.status === "parked" && <span className="xp-card-status parked">先放一放</span>}
          {expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        </button>
        <span className="xp-card-tools">
          {onEnlarge && <button type="button" title="放大到侧边" aria-label="放大到侧边" onClick={onEnlarge}><Maximize2 size={14} /></button>}
          {onPopout && <button type="button" title="在新窗口打开" aria-label="在新窗口打开讲解页" onClick={onPopout}><ExternalLink size={14} /></button>}
          {record && (
            <button type="button" title="下载为单个 HTML 文件" aria-label="下载讲解页 HTML"
              onClick={() => {
                if (!page.current) {
                  onToggle(true);
                  return;
                }
                downloadHtml(explainerHtml(page.current.querySelector(".xp-doc") as HTMLElement, { title: record.title, source: paperTitle }), record.title);
              }}>
              <Download size={14} />
            </button>
          )}
        </span>
      </header>
      {error && <p className="xp-inline-error" role="alert">{error}</p>}
      {expanded && record && (
        <div className="xp-card-body" ref={page}>
          {record.question && <p className="xp-card-question"><b>你的问题</b>{record.question}</p>}
          <ExplainerView doc={record.doc} disabled={disabled} onAnswer={ask} onPanelAsk={panelAsk} />
          {questSlot}
          <div className="xp-card-ask">
            <textarea
              ref={box}
              rows={1}
              value={draft}
              disabled={disabled}
              aria-label="接着问这一页"
              placeholder={disabled ? "教练正在回复…" : "接着问这一页，或点某一块右上角的按钮追问那一块"}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing && e.nativeEvent.keyCode !== 229) {
                  e.preventDefault();
                  ask(draft);
                }
              }}
            />
            <button type="button" className="primary" aria-label="发送追问" disabled={disabled || !draft.trim()} onClick={() => ask(draft)}>
              <ArrowUp size={15} />
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

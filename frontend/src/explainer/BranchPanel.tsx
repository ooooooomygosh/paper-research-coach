import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ArrowUp, CornerUpLeft, ExternalLink, MapPin } from "lucide-react";
import type { Row } from "../api";
import { ExplainerView } from "./ExplainerDoc";
import { useBranch } from "./useBranch";
import "./explainer.css";

type Props = {
  paper: Row;
  branchId: string;
  firstPageId?: string;
  // In its own browser window the panel fills it and has no floating frame.
  standalone?: boolean;
  onReturn: () => void;
  onPopout?: () => void;
  onLocate?: (anchor: any) => void;
  page?: number;
};

function mainlineLine(point?: { status: string; label: string }) {
  if (!point) return "";
  if (point.status === "completed") return "主线已完成";
  if (point.status === "active") return `主线停在「${point.label}」`;
  return "主线还没开始";
}

export default function BranchPanel({ paper, branchId, firstPageId, standalone, onReturn, onPopout, onLocate, page = 0 }: Props) {
  const { pages, record, currentId, setCurrentId, busy, error, ask } = useBranch(paper, branchId, firstPageId);
  const [text, setText] = useState("");
  const root = useRef<HTMLElement>(null);

  useEffect(() => {
    root.current?.focus({ preventScroll: true });
  }, []);
  useEffect(() => {
    if (record?.title && standalone) document.title = record.title + " · 讲解";
  }, [record?.title, standalone]);

  async function submit() {
    const value = text.trim();
    if (!value || busy) return;
    if (await ask(value, page)) setText("");
  }
  const point = record?.return_point;
  const quote = record?.anchor?.quote as string | undefined;

  const panel = (
    <aside
      ref={root}
      tabIndex={-1}
      className={"branch-panel" + (standalone ? " standalone" : "")}
      role="dialog"
      aria-modal="false"
      aria-label="讲解面板"
      onKeyDown={(e) => {
        if (e.key === "Escape" && !e.defaultPrevented) {
          e.preventDefault();
          e.stopPropagation();
          onReturn();
        }
      }}
    >
      <header className="branch-head">
        <div className="branch-title">
          <span className="branch-kicker">{record?.origin === "mainline" ? "主线图解" : "插话讲解"}</span>
          <h2>{record?.title || "正在准备讲解…"}</h2>
        </div>
        <div className="branch-actions">
          {onPopout && (
            <button className="branch-icon" title="在新窗口打开" aria-label="在新窗口打开" onClick={onPopout}>
              <ExternalLink size={16} />
            </button>
          )}
          <button className="primary branch-return" onClick={onReturn}>
            <CornerUpLeft size={15} />
            回到主线
          </button>
        </div>
      </header>
      {point && record?.origin !== "mainline" && (
        <p className="branch-mainline">
          <span>{mainlineLine(point)}</span>
          {point.status === "active" && point.pending_question && (
            <span title={point.pending_question}>· 待答：{point.pending_question}</span>
          )}
        </p>
      )}
      {pages.length > 1 && (
        <nav className="branch-pages" aria-label="这个问题的讲解页">
          {pages.map((p, i) => (
            <button key={p.id} aria-current={p.id === currentId ? "page" : undefined} title={p.title} onClick={() => setCurrentId(p.id)}>
              {i + 1}
            </button>
          ))}
        </nav>
      )}
      <div className="branch-body">
        {record?.question && (
          <p className="branch-question">
            <b>你的问题</b>
            {record.question}
          </p>
        )}
        {quote && (
          <blockquote className="branch-quote">
            {quote}
            {onLocate && (
              <button onClick={() => onLocate(record!.anchor)}>
                <MapPin size={12} />
                回到原文
              </button>
            )}
          </blockquote>
        )}
        {record ? (
          <ExplainerView doc={record.doc} onAnswer={(t) => void ask(t, page)} disabled={busy} />
        ) : (
          <p className="branch-wait" role="status">
            {error || "教练正在写讲解…"}
          </p>
        )}
        {busy && record && (
          <p className="branch-wait" role="status">
            教练正在写下一页…
          </p>
        )}
      </div>
      <footer className="branch-compose">
        {error && record && <p className="branch-error" role="alert">{error}</p>}
        <textarea
          aria-label="继续追问这一处"
          placeholder={busy ? "教练正在回复…" : "没懂的地方，接着问…（Enter 发送）"}
          rows={2}
          value={text}
          disabled={busy}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.altKey && !e.nativeEvent.isComposing && e.nativeEvent.keyCode !== 229) {
              e.preventDefault();
              void submit();
            }
          }}
        />
        <button className="primary" aria-label="发送追问" disabled={busy || !text.trim()} onClick={() => void submit()}>
          <ArrowUp size={16} />
        </button>
      </footer>
    </aside>
  );
  return standalone ? panel : createPortal(panel, document.body);
}

import { useEffect, useRef, useState } from "react";
import { BookOpen, Check, Circle, CircleDot, Download, ExternalLink, GitBranch, Lightbulb, MessageSquare, NotebookPen, RotateCcw, X } from "lucide-react";
import { api } from "./api";
import { downloadHtml, explainerHtml } from "./explainer/exportHtml";
import journeyCss from "./journey.css?raw";
import "./journey.css";

type Mark = { quote: string; page_index: number | null; message_id: string };
type Exchange = { text: string; reply: string; task?: string; page_index: number | null; message_id: string };
type SideQuest = {
  branch_id: string; title: string; question: string; gist: string; status: string; takeaway: string; pages: number;
  page_index: number | null;
};
type Leaves = {
  exchanges: Exchange[]; questions: Exchange[]; side_quests: SideQuest[];
  notes: { id: string; text: string; author: string; page_index: number | null; quote: string }[];
  ideas: { id: string; title: string; hypothesis: string; status: string }[];
  reviews: { id: string; prompt: string; page_index: number | null }[];
};
type Chapter = Leaves & {
  id: string; n: number; label: string; goal: string; check: string; status: "done" | "current" | "todo";
  takeaway: string; page_index: number | null; task: string; marks: Mark[];
};
export type Journey = {
  paper: { id: string; title: string; authors: string; year: string | number; goal: string };
  status: string;
  verdict: string;
  chapters: Chapter[];
  other: Leaves;
  counts: { chapters_done: number; chapters: number; side_quests: number; side_quests_done: number; answers: number };
};

const QUEST: Record<string, string> = { open: "进行中", done: "已弄懂", parked: "先放一放" };
const STATE: Record<string, string> = { done: "已完成", current: "进行中", todo: "未开始" };
const pageLabel = (i: number | null | undefined) => (Number.isInteger(i) ? `第 ${(i as number) + 1} 页` : "");
const hasLeaves = (x: Leaves) =>
  !!(x.exchanges.length || x.questions.length || x.side_quests.length || x.notes.length || x.ideas.length || x.reviews.length);

/**
 * The journey of one reading as a tree: the paper at the root, the eight chapters on the trunk,
 * and under each chapter what happened there — the passages the coach marked, the tasks with the
 * reader's own answers, the side quests and the notes. Everything is copied from the records;
 * nothing is scored. Clicking a node goes back to the page, the side quest or the conversation.
 */
export default function JourneyTree({
  paperId,
  onClose,
  onPage,
  onOpenQuest,
  onPopout,
  standalone = false,
}: {
  paperId: string;
  onClose?: () => void;
  onPage?: (pageIndex: number) => void;
  onOpenQuest?: (branchId: string) => void;
  onPopout?: () => void;
  standalone?: boolean;
}) {
  const [trip, setTrip] = useState<Journey | null>(null);
  const [error, setError] = useState("");
  const root = useRef<HTMLElement>(null);
  const tree = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let live = true;
    api("coach/journey/" + paperId)
      .then((t) => live && setTrip(t))
      .catch((e) => live && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      live = false;
    };
  }, [paperId]);
  useEffect(() => {
    if (!standalone) root.current?.focus();
  }, [standalone]);

  // In its own window the tree is a document: page numbers and titles are plain text there.
  const page = (i: number | null | undefined, label = pageLabel(i)) =>
    !Number.isInteger(i) || !label ? null : onPage ? (
      <button type="button" data-export="text" className="jt-page" onClick={() => onPage(i as number)}>
        {label}
      </button>
    ) : (
      <span className="jt-page">{label}</span>
    );

  const leaves = (x: Leaves) => (
    <>
      {x.exchanges.map((e) => (
        <li key={e.message_id} className="jt-leaf jt-answer">
          <MessageSquare size={13} aria-hidden="true" />
          <div>
            {e.task && <p className="jt-task"><b>任务</b>{e.task}</p>}
            <p className="jt-mine"><b>我的回答</b>{e.text}</p>
            {e.reply && <p className="jt-reply"><b>教练</b>{e.reply}</p>}
          </div>
        </li>
      ))}
      {x.questions.map((e) => (
        <li key={e.message_id} className="jt-leaf jt-question">
          <MessageSquare size={13} aria-hidden="true" />
          <div>
            <p className="jt-mine"><b>我问</b>{e.text} {page(e.page_index)}</p>
            {e.reply && <p className="jt-reply"><b>教练</b>{e.reply}</p>}
          </div>
        </li>
      ))}
      {x.side_quests.map((q) => (
        <li key={q.branch_id} className={"jt-leaf jt-side " + q.status + (q.status === "done" ? " key" : "")}>
          <GitBranch size={13} aria-hidden="true" />
          <div>
            <p className="jt-side-title">
              <span className="jt-chip">支线 · {QUEST[q.status] || q.status}</span>
              {onOpenQuest ? (
                <button type="button" data-export="text" className="jt-link" title="打开这页讲解" onClick={() => onOpenQuest(q.branch_id)}>
                  {q.title}
                </button>
              ) : (
                <b className="jt-link">{q.title}</b>
              )}
              {q.pages > 1 && <span className="jt-muted">{q.pages} 页</span>}
              {page(q.page_index)}
            </p>
            {q.question && <p className="jt-muted">问：{q.question}</p>}
            {q.takeaway ? <p className="jt-mine"><b>我的收获</b>{q.takeaway}</p> : q.gist && <p className="jt-reply"><b>讲解结论</b>{q.gist}</p>}
          </div>
        </li>
      ))}
      {x.notes.map((n) => (
        <li key={n.id} className="jt-leaf jt-note">
          <NotebookPen size={13} aria-hidden="true" />
          <div>
            {n.quote && <p className="jt-quote">“{n.quote}”</p>}
            <p className={n.author === "user" ? "jt-mine" : "jt-reply"}><b>{n.author === "user" ? "我的笔记" : "笔记"}</b>{n.text} {page(n.page_index)}</p>
          </div>
        </li>
      ))}
      {x.ideas.map((idea) => (
        <li key={idea.id} className="jt-leaf jt-idea">
          <Lightbulb size={13} aria-hidden="true" />
          <div><p className="jt-mine"><b>研究想法</b>{idea.title}</p>{idea.hypothesis && <p className="jt-muted">{idea.hypothesis}</p>}</div>
        </li>
      ))}
      {x.reviews.map((r) => (
        <li key={r.id} className="jt-leaf jt-review">
          <RotateCcw size={13} aria-hidden="true" />
          <div><p className="jt-mine"><b>复习题</b>{r.prompt} {page(r.page_index)}</p></div>
        </li>
      ))}
    </>
  );

  const chapter = (c: Chapter) => {
    const busy = !!(c.takeaway || c.marks.length || hasLeaves(c) || c.task);
    return (
      <li key={c.id} className={"jt-chapter " + c.status + (c.takeaway ? " key" : "")}>
        <span className="jt-node" aria-hidden="true">
          {c.status === "done" ? <Check size={13} /> : c.status === "current" ? <CircleDot size={13} /> : <Circle size={12} />}
        </span>
        <details open={busy}>
          <summary>
            <b>第 {c.n} 章 · {c.label}</b>
            <span className="jt-state">{STATE[c.status]}</span>
            {page(c.page_index)}
            {c.side_quests.length > 0 && <span className="jt-count"><GitBranch size={11} />{c.side_quests.length}</span>}
            {c.takeaway && <span className="jt-takeaway">{c.takeaway}</span>}
          </summary>
          <div className="jt-body">
            <p className="jt-goal">{c.check}</p>
            {c.task && <p className="jt-task"><b>当前任务</b>{c.task}</p>}
            {c.marks.length > 0 && (
              <ul className="jt-marks" aria-label={`第 ${c.n} 章标出的原文`}>
                {c.marks.map((m) => (
                  <li key={m.quote}>
                    <BookOpen size={12} aria-hidden="true" />
                    <span className="jt-quote">“{m.quote}”</span>
                    {page(m.page_index)}
                  </li>
                ))}
              </ul>
            )}
            {hasLeaves(c) && <ul className="jt-leaves">{leaves(c)}</ul>}
          </div>
        </details>
      </li>
    );
  };

  const exportTree = () => {
    if (!tree.current || !trip) return;
    downloadHtml(explainerHtml(tree.current, { title: "复盘树 · " + trip.paper.title, source: trip.paper.title, css: journeyCss }), "复盘树 " + trip.paper.title);
  };

  return (
    <aside
      ref={root}
      tabIndex={-1}
      className={"journey" + (standalone ? " standalone" : "")}
      role={standalone ? undefined : "dialog"}
      aria-modal={standalone ? undefined : "false"}
      aria-label="复盘树"
      onKeyDown={(e) => {
        if (e.key === "Escape" && onClose) {
          e.preventDefault();
          e.stopPropagation();
          onClose();
        }
      }}
    >
      <header className="journey-head">
        <div>
          <span className="branch-kicker">复盘树</span>
          <h2>{trip?.paper.title || "正在整理这篇论文的阅读…"}</h2>
          {trip && (
            <p className="journey-counts">
              主线 {trip.counts.chapters_done}/{trip.counts.chapters} 章 · 支线 {trip.counts.side_quests} 条（弄懂 {trip.counts.side_quests_done}）· 我的回答 {trip.counts.answers} 条
            </p>
          )}
        </div>
        <span className="journey-tools">
          {trip && (
            <button type="button" className="branch-icon" title="下载为单个 HTML 文件" aria-label="下载复盘树 HTML" onClick={exportTree}>
              <Download size={16} />
            </button>
          )}
          {onPopout && (
            <button type="button" className="branch-icon" title="在新窗口打开" aria-label="在新窗口打开复盘树" onClick={onPopout}>
              <ExternalLink size={16} />
            </button>
          )}
          {onClose && (
            <button type="button" className="branch-icon" aria-label="关闭复盘树" title="关闭" onClick={onClose}>
              <X size={16} />
            </button>
          )}
        </span>
      </header>
      {error && <p className="journey-error" role="alert">{error}</p>}
      {trip && (
        <div className="journey-tree" ref={tree}>
          <div className="jt-root">
            <span className="jt-root-kicker">论文{trip.paper.year ? ` · ${trip.paper.year}` : ""}</span>
            <b>{trip.paper.title}</b>
            {trip.verdict ? (
              <p className="jt-verdict"><b>我的核心判断</b>{trip.verdict}</p>
            ) : (
              <p className="jt-muted">读完第 6 章“边界与判断”后，你的核心判断会出现在这里。</p>
            )}
          </div>
          <ol className="jt-trunk">{trip.chapters.map(chapter)}</ol>
          {hasLeaves(trip.other) && (
            <section className="jt-other" aria-label="主线之外">
              <h3>主线之外</h3>
              <ul className="jt-leaves">{leaves(trip.other)}</ul>
            </section>
          )}
          <p className="jt-legend">
            <span className="jt-legend-key" aria-hidden="true" />关键节点：有收获的章节和弄懂的支线。回答和收获是你的原话；“教练”一行是那条回复的第一句。
          </p>
        </div>
      )}
    </aside>
  );
}

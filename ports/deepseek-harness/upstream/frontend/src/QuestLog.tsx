import { useEffect, useRef } from "react";
import { Check, CircleDot, Circle, GitBranch, Network, Pause, X } from "lucide-react";
import type { ExplainerSummary } from "./explainer/types";

const STATUS: Record<string, string> = { open: "进行中", done: "已弄懂", parked: "先放一放" };

export type SideQuest = ExplainerSummary & { pages: number };

/** Side quests (one per branch) grouped under the chapter where the mainline paused. */
export function sideQuestsOf(list: ExplainerSummary[]): SideQuest[] {
  const pages: Record<string, number> = {};
  for (const p of list) if (p.origin !== "mainline") pages[p.branch_id] = (pages[p.branch_id] || 0) + 1;
  return list
    .filter((p) => p.origin !== "mainline" && p.id === p.branch_id)
    .map((p) => ({ ...p, pages: pages[p.id] || 1 }));
}

export function chapterOf(q: ExplainerSummary) {
  return q.return_point?.status === "active" ? q.return_point.step : "";
}

/**
 * The quest log: the eight mainline chapters with their state and takeaway, and under each one
 * the side quests opened while it was the current chapter. Nothing here is a score.
 */
export default function QuestLog({ flow, quests, onClose, onOpenQuest, onPage, onJourney }: {
  flow: any;
  quests: SideQuest[];
  onClose: () => void;
  onOpenQuest: (q: SideQuest) => void;
  onPage: (pageIndex: number) => void;
  onJourney?: () => void;
}) {
  const root = useRef<HTMLElement>(null);
  useEffect(() => root.current?.focus(), []);
  const steps: { id: string; label: string }[] = flow?.steps || [];
  const completed: Record<string, any> = Object.fromEntries((flow?.completed || []).map((c: any) => [c.step, c]));
  const active = flow?.status === "active" || flow?.status === "completed";
  const loose = quests.filter((q) => !steps.some((s) => s.id === chapterOf(q)));
  const done = quests.filter((q) => q.quest?.status === "done").length;

  const questItem = (q: SideQuest) => (
    <li key={q.id} className={"quest-log-side " + (q.quest?.status || "open")}>
      <button type="button" onClick={() => onOpenQuest(q)} title="在对话里打开这页讲解">
        <span className="quest-log-chip">{STATUS[q.quest?.status || "open"]}</span>
        <b>{q.title}</b>
        {q.pages > 1 && <span className="quest-log-pages">{q.pages} 页</span>}
        {q.question && <span className="quest-log-question">问：{q.question}</span>}
        {q.quest?.takeaway ? (
          <span className="quest-log-takeaway">我的收获：{q.quest.takeaway}</span>
        ) : (
          q.gist && <span className="quest-log-gist">{q.gist}</span>
        )}
      </button>
    </li>
  );

  return (
    <aside
      ref={root}
      tabIndex={-1}
      className="quest-log"
      role="dialog"
      aria-modal="false"
      aria-label="任务日志"
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.preventDefault();
          e.stopPropagation();
          onClose();
        }
      }}
    >
      <header className="quest-log-head">
        <div>
          <span className="branch-kicker">任务日志</span>
          <h2>主线 {Object.keys(completed).length}/{steps.length || 8} 章 · 支线 {quests.length} 条{quests.length ? `（弄懂 ${done}）` : ""}</h2>
        </div>
        <span className="quest-log-tools">
          {onJourney && (
            <button type="button" className="primary" onClick={onJourney}><Network size={14} />复盘树</button>
          )}
          <button type="button" className="branch-icon" aria-label="关闭任务日志" title="关闭" onClick={onClose}><X size={16} /></button>
        </span>
      </header>
      <ol className="quest-log-chapters">
        {steps.map((s, i) => {
          const c = completed[s.id];
          const current = active && !c && s.id === flow?.current;
          const side = quests.filter((q) => chapterOf(q) === s.id);
          return (
            <li key={s.id} className={"quest-log-chapter" + (c ? " done" : current ? " current" : "")} aria-current={current ? "step" : undefined}>
              <div className="quest-log-node" aria-hidden="true">
                {c ? <Check size={13} /> : current ? <CircleDot size={13} /> : <Circle size={13} />}
              </div>
              <div className="quest-log-main">
                <p className="quest-log-title">
                  <b>第 {i + 1} 章 · {s.label}</b>
                  <span>{c ? "已完成" : current ? "进行中" : "未开始"}</span>
                  {c && Number.isInteger(c.page_index) && (
                    <button type="button" className="quest-log-page" onClick={() => onPage(c.page_index)}>第 {c.page_index + 1} 页</button>
                  )}
                </p>
                {c?.takeaway && <p className="quest-log-takeaway">收获：{c.takeaway}</p>}
                {current && flow?.pending_question && <p className="quest-log-task">任务：{flow.pending_question}</p>}
                {side.length > 0 && (
                  <ul className="quest-log-sides" aria-label={`第 ${i + 1} 章的支线`}>
                    <GitBranch size={13} className="quest-log-branch-icon" aria-hidden="true" />
                    {side.map(questItem)}
                  </ul>
                )}
              </div>
            </li>
          );
        })}
      </ol>
      {loose.length > 0 && (
        <section className="quest-log-loose" aria-label="开读之前的支线">
          <h3><Pause size={13} />开读主线之前的支线</h3>
          <ul className="quest-log-sides">{loose.map(questItem)}</ul>
        </section>
      )}
      {!quests.length && <p className="quest-log-empty">还没有支线。读到不懂的地方，选中文字直接问，就会开一条支线。</p>}
    </aside>
  );
}

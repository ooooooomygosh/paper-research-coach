import type { ReactNode } from "react";
import { BookOpenCheck, Flag, Quote } from "lucide-react";

export const CIRCLED = "①②③④⑤⑥⑦⑧⑨";

/** Make ①②③ in a reply clickable when the reply marked sentences in the PDF. */
export function linkMarks(text: string) {
  return text.replace(/[①②③④⑤⑥⑦⑧⑨]/g, (c) => `[${c}](#mark-${CIRCLED.indexOf(c) + 1})`);
}

/** The marks of a reply, in order, with the action that draws them. */
export function marksOf(actions: any[] = []) {
  return actions
    .filter((a) => a.kind === "focus")
    .flatMap((a) => (a.marks || []).map((m: any) => ({ action: a, n: m.n as number, quote: m.quote as string, page: a.anchor?.page_index as number })));
}

/**
 * A mainline reply drawn as a quest card: the chapter, the sentences to look at, the coach's text
 * (its first paragraph is the conclusion), any figure, the task it sets and a chapter-complete note.
 * Everything comes from data the reply already carries; the model writes nothing extra for it.
 */
export default function QuestCard({
  chapter,
  total,
  label,
  actions,
  onMark,
  body,
  figures,
  task,
  completed,
  finale,
}: {
  chapter: number;
  total: number;
  label: string;
  actions: any[];
  onMark: (action: any) => void;
  body: ReactNode;
  figures?: ReactNode;
  task?: ReactNode;
  completed?: { label: string; takeaway: string } | null;
  /** After the last chapter: the way to the journey tree. */
  finale?: ReactNode;
}) {
  const marks = marksOf(actions);
  return (
    <div className="quest-card">
      <div className="quest-head">
        <Flag size={13} />
        <span>主线 · 第 {chapter}/{total} 章</span>
        <b>{label}</b>
      </div>
      {marks.length > 0 && (
        <div className="quest-look" aria-label="看这里">
          {marks.map((m) => (
            <button key={m.action.id + m.n} type="button" className="quest-quote" onClick={() => onMark(m.action)} title="在 PDF 里看这一句">
              <span className="quest-quote-n">{CIRCLED[m.n - 1] || m.n}</span>
              <q>{m.quote}</q>
              <small><Quote size={11} />第 {m.page + 1} 页</small>
            </button>
          ))}
        </div>
      )}
      <div className="quest-body">{body}</div>
      {figures}
      {task}
      {completed && (
        <p className="quest-done" role="status">
          <BookOpenCheck size={15} />
          <span><b>第 {chapter} 章「{completed.label}」完成</b>{completed.takeaway && <> · 收获：{completed.takeaway}</>}</span>
        </p>
      )}
      {finale}
    </div>
  );
}

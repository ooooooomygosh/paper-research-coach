import type { Row } from "./api";

export type ReplyIntent = "answer" | "detour";
export type IntentChoice = "auto" | ReplyIntent;
export type HelpMode = "guided" | "hint" | "explain" | "challenge";
export const helpLabels: Record<HelpMode, string> = {
  guided: "一起推敲", hint: "只给提示", explain: "直接解释", challenge: "检验我的判断",
};

export function replyIntent(flow: any, anchor: any, choice: IntentChoice): ReplyIntent {
  if (choice !== "auto") return choice;
  // A fresh selection is a deliberate detour; a reply to a pending mainline
  // question should not require discovering a second, different Send button.
  return !anchor && flow?.status === "active" && flow?.pending_question ? "answer" : "detour";
}

export function contextPage(paper: Row, page: number, anchor: any): number {
  if (!anchor) return page;
  if (anchor.paper_id !== paper.id || anchor.source_version !== paper.source_version || anchor.status === "stale")
    throw new Error("选区属于另一篇论文或旧版本，请移除后重新选择。");
  if (anchor.rendition && anchor.page_index == null)
    throw new Error("这处译文尚未对应原文。可先保存批注，或选中对应原文再讨论。");
  const target = anchor.page_index ?? page;
  if (!Number.isInteger(target) || target < 0 || target >= paper.page_count)
    throw new Error("选区页码无效，请重新选择。");
  return target;
}

export function imageMatchesPage(paper: Row, page: number, anchor: any): boolean {
  return !anchor || (anchor.paper_id === paper.id && anchor.source_version === paper.source_version &&
    anchor.status === "verified" && anchor.page_index === page);
}

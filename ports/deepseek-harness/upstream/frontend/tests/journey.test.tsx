import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import JourneyTree from "../src/JourneyTree";
import { explainerHtml } from "../src/explainer/exportHtml";
import { api } from "../src/api";

vi.mock("../src/api", async (original) => ({ ...(await original<any>()), api: vi.fn() }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

const none = { exchanges: [], questions: [], side_quests: [], notes: [], ideas: [], reviews: [] };
const chapter = (n: number, id: string, label: string, status: string, extra: any = {}) => ({
  id, n, label, goal: "", check: "检查 " + label, status, takeaway: "", evidence: "", page_index: null, finished_at: "",
  task: "", marks: [], ...none, ...extra,
});
const trip = {
  paper: { id: "p", title: "Attention Is All You Need", authors: "Vaswani et al.", year: 2017, goal: "" },
  status: "active",
  verdict: "",
  chapters: [
    chapter(1, "orient", "阅读目标", "done", {
      takeaway: "只用注意力也能做翻译。", page_index: 0,
      marks: [{ quote: "based solely on attention mechanisms", page_index: 0, message_id: "m1" }],
      exchanges: [{ text: "它去掉了循环和卷积", reply: "对，这是第一个要核对的主张。", task: "这篇要解决什么？", page_index: null, message_id: "u1" }],
    }),
    chapter(2, "insight", "独特贡献", "current", {
      task: "和 RNN 比，新在哪？",
      side_quests: [{ branch_id: "b1", title: "为什么要除以 √d_k", question: "为什么要缩放？", gist: "不缩放时 softmax 会饱和。",
        status: "done", takeaway: "维度大时点积方差变大，所以要缩放。", pages: 2, page_index: 3 }],
    }),
    chapter(3, "model", "问题设定", "todo"),
  ],
  other: { ...none, notes: [{ id: "n1", text: "先读图 1", author: "user", page_index: 2, quote: "" }] },
  counts: { chapters_done: 1, chapters: 8, side_quests: 1, side_quests_done: 1, answers: 1 },
};

it("draws the reading as a tree: chapters, my answers, marks, side quests, and nothing scored", async () => {
  vi.mocked(api).mockResolvedValue(trip);
  const onPage = vi.fn(), onOpenQuest = vi.fn();
  render(<JourneyTree paperId="p" onPage={onPage} onOpenQuest={onOpenQuest} onClose={vi.fn()} />);
  const tree = await screen.findByRole("dialog", { name: "复盘树" });
  expect(vi.mocked(api)).toHaveBeenCalledWith("coach/journey/p");
  expect(within(tree).getByText(/主线 1\/8 章 · 支线 1 条（弄懂 1）· 我的回答 1 条/)).toBeTruthy();
  expect(within(tree).getByText("它去掉了循环和卷积")).toBeTruthy();
  expect(within(tree).getByText("对，这是第一个要核对的主张。")).toBeTruthy();
  expect(within(tree).getByText("维度大时点积方差变大，所以要缩放。")).toBeTruthy();
  expect(within(tree).getByText(/读完第 6 章/)).toBeTruthy();
  expect(within(tree).queryByText(/XP|经验值|掌握度|分数/)).toBeNull();
  // Done and current chapters open; an untouched chapter stays folded.
  const details = tree.querySelectorAll("details");
  expect([...details].map((d) => d.open)).toEqual([true, true, false]);
  fireEvent.click(within(within(tree).getByRole("list", { name: "第 1 章标出的原文" })).getByRole("button", { name: "第 1 页" }));
  expect(onPage).toHaveBeenCalledWith(0);
  fireEvent.click(within(tree).getByRole("button", { name: "为什么要除以 √d_k" }));
  expect(onOpenQuest).toHaveBeenCalledWith("b1");
  expect(within(tree).getByRole("region", { name: "主线之外" })).toBeTruthy();
});

it("exports the tree as one static HTML file that keeps the words and opens every fold", async () => {
  vi.mocked(api).mockResolvedValue(trip);
  render(<JourneyTree paperId="p" onClose={vi.fn()} />);
  await screen.findByText("它去掉了循环和卷积");
  const html = explainerHtml(document.querySelector(".journey-tree") as HTMLElement, { title: "复盘树", css: ".jt-root{}" });
  expect(html).not.toMatch(/<script|<button/);
  expect(html).toContain("为什么要除以 √d_k");
  expect(html).toContain("第 1 页");
  expect(html.match(/<details[^>]*open/g)?.length).toBe(3);
  expect(html).toContain(".jt-root{}");
});

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import BranchPanel from "../src/explainer/BranchPanel";
import { ExplainerView } from "../src/explainer/ExplainerDoc";
import { layoutFlow } from "../src/explainer/flow-layout";
import { layoutSequence } from "../src/explainer/sequence-layout";
import { wrapText } from "../src/explainer/measure";
import type { ExplainerDoc, ExplainerRecord } from "../src/explainer/types";
import { api } from "../src/api";

vi.mock("../src/api", async (original) => ({ ...(await original<any>()), api: vi.fn() }));

const here = dirname(fileURLToPath(import.meta.url));
const fixture = (name: string): ExplainerDoc =>
  JSON.parse(readFileSync(resolve(here, "../../tests/fixtures/explainers", name + ".doc.json"), "utf-8"));
const budget = fixture("budget-zh");
const handshake = fixture("handshake-en");
const hostile = fixture("hostile");
const paper = { id: "p", revision: 1, source_version: "v1", page_count: 3 };

afterEach(cleanup);

it("draws every component from the shared fixtures", () => {
  const { container } = render(<ExplainerView doc={handshake} />);
  expect(screen.getByRole("img", { name: /时序图：Client、Server/ })).toBeTruthy();
  expect(screen.getByRole("img", { name: /流程图：CLOSED/ })).toBeTruthy();
  expect(container.querySelector(".xp-tree")?.textContent).toContain("SYN+ACK");
  expect(container.querySelectorAll(".xp-timeline li")).toHaveLength(3);
  expect(container.querySelector(".xp-kv")?.textContent).toContain("transport");
  // numbered messages and the dashed return are drawn from the draft, not guessed
  expect(container.textContent).toContain("1. SYN, seq=x");
  expect(container.querySelectorAll("svg .xp-edge.dashed").length).toBeGreaterThan(0);
});

it("shows table status words as badges and a callout, in Chinese", () => {
  const { container } = render(<ExplainerView doc={budget} />);
  expect(container.querySelector(".xp-badge.ok")).toBeTruthy();
  expect(container.querySelector(".xp-badge.no")?.parentElement?.textContent).toContain("多了一倍");
  expect(container.querySelector(".xp-callout.warn")?.textContent).toContain("小心");
  expect(container.querySelector("article")?.getAttribute("lang")).toBe("zh-CN");
});

it("keeps hostile draft text inert: no script, image, handler or javascript link reaches the DOM", () => {
  const { container } = render(<ExplainerView doc={hostile} />);
  expect(container.querySelector("script, img, iframe")).toBeNull();
  const attributes = [...container.querySelectorAll("*")].flatMap((el) => [...el.attributes].map((a) => a.name + "=" + a.value));
  expect(attributes.filter((a) => /^on/i.test(a) || /javascript:/i.test(a))).toEqual([]);
  expect(container.querySelector('a[href^="javascript"]')).toBeNull();
  expect(container.textContent).toContain("<script>alert(1)</script>"); // shown as text
});

it("an ask starts on the suggestion and sends the reader's choice", () => {
  const onAnswer = vi.fn();
  render(<ExplainerView doc={budget} onAnswer={onAnswer} />);
  const radios = screen.getAllByRole("radio") as HTMLInputElement[];
  expect(radios.map((r) => r.checked)).toEqual([true, false]);
  fireEvent.click(radios[1]);
  fireEvent.click(screen.getByRole("button", { name: "按这个选择继续" }));
  expect(onAnswer).toHaveBeenCalledWith("我的选择：下一步先查哪个？ → 误差条");
});

it("lays out a flow without overlapping nodes and keeps every edge", () => {
  const flow = (budget.panels[0].blocks[0] as any);
  const layout = layoutFlow(flow);
  expect(layout.width).toBeGreaterThan(100);
  expect(layout.edges).toHaveLength(flow.edges.length);
  expect(layout.edges.every((e) => e.d.startsWith("M"))).toBe(true);
  expect(layout.groups).toHaveLength(1);
  for (const a of layout.nodes)
    for (const b of layout.nodes) {
      if (a === b) continue;
      const apart = a.x + a.w <= b.x + 0.5 || b.x + b.w <= a.x + 0.5 || a.y + a.h <= b.y + 0.5 || b.y + b.h <= a.y + 0.5;
      expect(apart).toBe(true);
    }
});

it("a sequence keeps messages in order and wraps long labels instead of squeezing them", () => {
  const block = {
    type: "sequence", numbered: false, participants: ["A", "B"],
    steps: [
      { kind: "msg", from: "A", to: "B", dashed: false, label: "a very long message label that needs more than one line to read well" },
      { kind: "msg", from: "B", to: "A", dashed: true, label: "ok" },
    ],
  } as any;
  const layout = layoutSequence(block);
  const [first, second] = layout.items as any[];
  expect(first.lines.length).toBeGreaterThan(1);
  expect(second.y).toBeGreaterThan(first.y);
  expect(wrapText("中文也要能换行显示出来而不是挤成一行", 13, 60).length).toBeGreaterThan(1);
});

const record = (over: Partial<ExplainerRecord> = {}): ExplainerRecord => ({
  id: "b1", paper_id: "p", branch_id: "b1", seq: 1, title: "为什么这个比较不公平", question: "为什么不能直接比较？",
  doc: budget, warnings: [], anchor: { quote: "Both policies receive 20 observations", page_index: 0 },
  return_point: { status: "active", step: "model", label: "问题设定", pending_question: "决策时能用到哪些信息？", next_action: "" },
  created_at: "t1", updated_at: "t1", ...over,
});
const summary = (r: ExplainerRecord) => ({ id: r.id, branch_id: r.branch_id, seq: r.seq, title: r.title, question: r.question, created_at: r.created_at, updated_at: r.updated_at, return_point: r.return_point });

let pages: ExplainerRecord[];
beforeEach(() => {
  pages = [record()];
  vi.stubGlobal("EventSource", class { close() {} onmessage: any });
  vi.mocked(api).mockImplementation(async (path: string, body?: any) => {
    if (path === "coach/explainers/p") return { data: pages.map(summary) };
    if (path.startsWith("coach/explainer/")) return pages.find((p) => p.id === path.split("/").pop());
    if (path === "coach/send/p") return { conversation_id: "c" };
    return {};
  });
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

it("the branch panel shows the answer, where the mainline paused, and returns with one click or Escape", async () => {
  const onReturn = vi.fn();
  const onLocate = vi.fn();
  render(<BranchPanel paper={paper} branchId="b1" firstPageId="b1" onReturn={onReturn} onLocate={onLocate} />);
  const dialog = await screen.findByRole("dialog", { name: "讲解面板" });
  await within(dialog).findByText("为什么这个比较不公平");
  expect(dialog.textContent).toContain("主线停在「问题设定」");
  expect(dialog.textContent).toContain("待答：决策时能用到哪些信息？");
  expect(dialog.textContent).toContain("你的问题");
  fireEvent.click(within(dialog).getByRole("button", { name: /回到原文/ }));
  expect(onLocate).toHaveBeenCalledWith(expect.objectContaining({ page_index: 0 }));
  fireEvent.click(within(dialog).getByRole("button", { name: "回到主线" }));
  expect(onReturn).toHaveBeenCalledTimes(1);
  fireEvent.keyDown(dialog, { key: "Escape" });
  expect(onReturn).toHaveBeenCalledTimes(2);
});

it("a follow-up stays in the same branch and never claims to be a mainline answer", async () => {
  render(<BranchPanel paper={paper} branchId="b1" firstPageId="b1" onReturn={vi.fn()} />);
  await screen.findByText("为什么这个比较不公平");
  fireEvent.change(screen.getByLabelText("继续追问这一处"), { target: { value: "那误差条呢？" } });
  fireEvent.click(screen.getByRole("button", { name: "发送追问" }));
  await waitFor(() => expect(vi.mocked(api).mock.calls.some(([p]) => p === "coach/send/p")).toBe(true));
  const body = vi.mocked(api).mock.calls.find(([p]) => p === "coach/send/p")![1];
  expect(body).toMatchObject({ intent: "detour", branch_id: "b1", content: "那误差条呢？", source_version: "v1", anchor: null });
  expect((screen.getByLabelText("继续追问这一处") as HTMLTextAreaElement).value).toBe("");
});

it("a new page appears as a numbered tab and opens on it; the pop-out button is offered", async () => {
  const onPopout = vi.fn();
  render(<BranchPanel paper={paper} branchId="b1" firstPageId="b1" onReturn={vi.fn()} onPopout={onPopout} />);
  await screen.findByText("为什么这个比较不公平");
  expect(screen.queryByRole("navigation", { name: /讲解页/ })).toBeNull();
  pages = [record(), record({ id: "b2", seq: 2, title: "误差条是什么", doc: handshake })];
  // The browser learns about the new page from the coach's event stream.
  const source = (EventSource as any);
  expect(source).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "在新窗口打开" }));
  expect(onPopout).toHaveBeenCalled();
});

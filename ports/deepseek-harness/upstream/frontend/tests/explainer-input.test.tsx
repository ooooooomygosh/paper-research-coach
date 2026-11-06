import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import BranchPanel from "../src/explainer/BranchPanel";
import ExplainerCard from "../src/explainer/ExplainerCard";
import { layoutSequence } from "../src/explainer/sequence-layout";
import { api } from "../src/api";

// What the reader types, and what they asked to download, must survive a failed or repeated request.
vi.mock("../src/api", async (original) => ({ ...(await original<any>()), api: vi.fn() }));

const here = dirname(fileURLToPath(import.meta.url));
const doc = JSON.parse(readFileSync(resolve(here, "../../tests/fixtures/explainers/budget-zh.doc.json"), "utf8"));
const paper = { id: "p", revision: 1, source_version: "v1", page_count: 3 };
const record = {
  id: "x1", branch_id: "x1", seq: 1, title: doc.title, question: "预算一样吗？", doc, warnings: [], anchor: null,
  created_at: "t1", updated_at: "t1", return_point: null, paper_id: "p",
};
const summary = { id: "x1", branch_id: "x1", seq: 1, title: doc.title, question: "q", created_at: "t1", updated_at: "t1", return_point: null };

class FakeEventSource {
  static last: FakeEventSource | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  constructor() { FakeEventSource.last = this; }
  close() {}
  emit(snapshot: object) { act(() => this.onmessage?.({ data: JSON.stringify(snapshot) })); }
}

beforeEach(() => {
  FakeEventSource.last = null;
  vi.stubGlobal("EventSource", FakeEventSource);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

it("keeps the follow-up the reader typed when sending it fails", async () => {
  vi.mocked(api).mockResolvedValue(record);
  const onAsk = vi.fn().mockResolvedValue(false); // the host could not send it (for example a 409)
  render(<ExplainerCard id="x1" branchId="x1" expanded onToggle={vi.fn()} onAsk={onAsk} />);
  const box = (await screen.findByLabelText("接着问这一页")) as HTMLTextAreaElement;
  fireEvent.change(box, { target: { value: "一个很长的、认真写下的追问" } });
  fireEvent.click(screen.getByRole("button", { name: "发送追问" }));
  await waitFor(() => expect(onAsk).toHaveBeenCalled());
  await act(async () => {});
  expect(box.value).toBe("一个很长的、认真写下的追问");
});

it("clears the follow-up once it was sent", async () => {
  vi.mocked(api).mockResolvedValue(record);
  const onAsk = vi.fn().mockResolvedValue(true);
  render(<ExplainerCard id="x1" branchId="x1" expanded onToggle={vi.fn()} onAsk={onAsk} />);
  const box = (await screen.findByLabelText("接着问这一页")) as HTMLTextAreaElement;
  fireEvent.change(box, { target: { value: "再问一个" } });
  fireEvent.click(screen.getByRole("button", { name: "发送追问" }));
  await waitFor(() => expect(box.value).toBe(""));
});

it("a collapsed card downloads after it opens, instead of only opening", async () => {
  vi.mocked(api).mockResolvedValue(record);
  const create = vi.fn(() => "blob:x");
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: create, revokeObjectURL: vi.fn() }));
  function Host() {
    const [open, setOpen] = useState(false);
    return <ExplainerCard id="x1" branchId="x1" expanded={open} onToggle={setOpen} onAsk={vi.fn()} />;
  }
  render(<Host />);
  fireEvent.click(await screen.findByRole("button", { name: "下载讲解页 HTML" }));
  await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
});

it("pressing Enter twice before the reply arrives sends one follow-up, not two", async () => {
  let release: (v: unknown) => void = () => {};
  vi.mocked(api).mockImplementation(async (path: string) => {
    if (path === "coach/explainers/p") return { data: [summary] };
    if (path.startsWith("coach/explainer/")) return record;
    if (path === "coach/send/p") return new Promise((r) => (release = r));
    return {};
  });
  render(<BranchPanel paper={paper} branchId="x1" firstPageId="x1" onReturn={vi.fn()} />);
  await screen.findByRole("dialog", { name: "讲解面板" });
  const box = await screen.findByLabelText("继续追问这一处");
  fireEvent.change(box, { target: { value: "那误差条呢？" } });
  fireEvent.keyDown(box, { key: "Enter" });
  fireEvent.keyDown(box, { key: "Enter" });
  const sends = () => vi.mocked(api).mock.calls.filter(([p]) => p === "coach/send/p").length;
  await waitFor(() => expect(sends()).toBeGreaterThan(0));
  expect(sends()).toBe(1);
  release({});
});

it("drops an old load error once a later load succeeds", async () => {
  let fail = true;
  vi.mocked(api).mockImplementation(async (path: string) => {
    if (path === "coach/explainers/p") {
      if (fail) throw new Error("服务暂时不可用");
      return { data: [summary] };
    }
    if (path.startsWith("coach/explainer/")) return record;
    return {};
  });
  render(<BranchPanel paper={paper} branchId="x1" firstPageId="x1" onReturn={vi.fn()} />);
  await act(async () => {});
  fail = false;
  FakeEventSource.last!.emit({ busy: true, messages: [] });
  FakeEventSource.last!.emit({ busy: false, messages: [] });
  await screen.findByText(doc.title);
  expect(screen.queryByRole("alert")).toBeNull();
});

it("a sequence note that names nobody is drawn across all participants, not as NaN", () => {
  const layout = layoutSequence({
    type: "sequence", participants: ["A", "B"], numbered: false,
    steps: [{ kind: "note", over: [], text: "hello" }],
  } as any);
  const note = layout.items[0] as any;
  expect(Number.isFinite(note.x)).toBe(true);
  expect(Number.isFinite(note.w)).toBe(true);
  expect(note.w).toBeGreaterThan(0);
});

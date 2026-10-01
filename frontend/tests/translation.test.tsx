import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { TranslationPopover, TranslationTools } from "../src/ReadingTools";
import { api } from "../src/api";
vi.mock("../src/api", async (original) => ({
  ...(await original<any>()),
  api: vi.fn(),
}));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  localStorage.clear();
});
it("looks up saved translation and discusses the original anchor", async () => {
  const original = {
    paper_id: "p",
    source_version: "v",
    page_index: 4,
    quote: "Original evidence",
    rects: [[40, 50, 100, 60]],
    status: "verified",
  };
  const discuss = vi.fn();
  vi.mocked(api).mockResolvedValue({
    status: "ready",
    level: "paragraph",
    text: "已有的中文译文。",
    source_anchor: original,
  });
  render(
    <TranslationPopover
      selection={{
        anchor: { ...original, quote: "中文选句" },
        view: "dual",
        x: 30,
        y: 40,
      }}
      job={{ id: "translated", state: "completed" }}
      onClose={vi.fn()}
      onSource={vi.fn()}
      onDiscuss={discuss}
    />,
  );
  await screen.findByText("已有的中文译文。");
  expect(screen.getByText("对应段落")).toBeTruthy();
  fireEvent.click(screen.getByText("讨论这处"));
  expect(discuss).toHaveBeenCalledWith(original);
  expect(vi.mocked(api).mock.calls.map(([path]) => path)).toEqual([
    "translation/jobs/translated/selection",
  ]);
});
it("previews source without requiring translation and closes the topmost layer with Escape", () => {
  const close = vi.fn();
  const underlying = vi.fn();
  document.addEventListener("keydown", underlying);
  render(
    <TranslationPopover
      selection={{
        anchor: { quote: "Original" },
        view: "original",
        x: 30,
        y: 40,
      }}
      job={null}
      onClose={close}
      onSource={vi.fn()}
      onDiscuss={vi.fn()}
    />,
  );
  expect(
    screen.getByText("可以直接讨论这句话，不需要先翻译整篇论文。"),
  ).toBeTruthy();
  fireEvent.keyDown(document, { key: "Escape" });
  expect(close).toHaveBeenCalledOnce();
  expect(underlying).not.toHaveBeenCalled();
  document.removeEventListener("keydown", underlying);
});
it("retains the request identifier when translation start loses its response", async () => {
  vi.mocked(api).mockImplementation(async (path) => {
    if (path === "translation/settings")
      return {
        model: "gpt-6-luna",
        effort: "low",
        lang_in: "en",
        lang_out: "zh-CN",
        component: { ready: true },
      };
    if (path === "coach/status")
      return {
        models: [
          {
            model: "gpt-6-luna",
            supportedReasoningEfforts: [{ reasoningEffort: "low" }],
          },
        ],
      };
    throw new Error("Connection interrupted");
  });
  render(
    <TranslationTools
      paper={{ id: "p", source_version: "v" }}
      job={null}
      reload={vi.fn()}
      open
    />,
  );
  await screen.findByLabelText("翻译模型");
  fireEvent.click(screen.getByText("生成整篇双语 PDF"));
  await screen.findByRole("alert");
  const first = vi
    .mocked(api)
    .mock.calls.find(([path]) => path === "translation/p/jobs")![1];
  fireEvent.click(screen.getByText("生成整篇双语 PDF"));
  await waitFor(() =>
    expect(
      vi
        .mocked(api)
        .mock.calls.filter(([path]) => path === "translation/p/jobs"),
    ).toHaveLength(2),
  );
  expect(
    vi
      .mocked(api)
      .mock.calls.filter(([path]) => path === "translation/p/jobs")[1][1]
      .operation_id,
  ).toBe(first.operation_id);
  expect(
    vi.mocked(api).mock.calls.some(([path]) => path === "coach/send/p"),
  ).toBe(false);
});

it("keeps translated geometry when a source match arrives and saves an unmapped region", async () => {
  const rendition = { job_id: "translated", view: "dual", document_version: "a".repeat(64), page_index: 0, quote: "", rects: [[650, 100, 800, 200]] };
  const anchor = { paper_id: "p", source_version: "v", page_index: null, rects: [], status: "unresolved", rendition };
  const mark = vi.fn().mockResolvedValue(undefined);
  render(<TranslationPopover selection={{ anchor, view: "dual", x: 10, y: 10 }} job={{ id: "translated", state: "completed" }} onClose={vi.fn()} onSource={vi.fn()} onDiscuss={vi.fn()} onMark={mark} />);
  expect(screen.getByRole("dialog", { name: "区域批注" })).toBeTruthy();
  fireEvent.click(screen.getByText("保留标记"));
  await screen.findByText("已保留在 PDF");
  expect(mark).toHaveBeenCalledWith(anchor);
  expect(vi.mocked(api)).not.toHaveBeenCalled();
  expect((screen.getByText("讨论这处") as HTMLButtonElement).disabled).toBe(true);
});

it("preserves both source evidence and the exact translated selection for marking", async () => {
  const rendition = { job_id: "translated", view: "mono", document_version: "a".repeat(64), page_index: 0, quote: "中文原话", rects: [[50, 100, 200, 130]] };
  const anchor = { paper_id: "p", source_version: "v", page_index: null, rects: [], status: "unresolved", rendition };
  const original = { paper_id: "p", source_version: "v", page_index: 0, quote: "Source evidence", rects: [[40, 80, 160, 90]], status: "verified" };
  vi.mocked(api).mockResolvedValue({ status: "ready", text: "中文对应句", source_anchor: original });
  const mark = vi.fn().mockResolvedValue(undefined);
  render(<TranslationPopover selection={{ anchor, view: "mono", x: 10, y: 10 }} job={{ id: "translated", state: "completed" }} onClose={vi.fn()} onSource={vi.fn()} onDiscuss={vi.fn()} onMark={mark} />);
  await screen.findByText("中文对应句");
  fireEvent.click(screen.getByText("保留标记"));
  await screen.findByText("已保留在 PDF");
  expect(mark).toHaveBeenCalledWith({ ...original, rendition });
});

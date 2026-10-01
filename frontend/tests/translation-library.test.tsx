import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import TranslationLibrary, {
  TranslationBadge,
} from "../src/TranslationLibrary";
import { TranslationTools } from "../src/ReadingTools";
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
const profile = {
  model: "gpt-6-luna",
  effort: "low",
  lang_in: "en",
  lang_out: "zh-CN",
  paper_concurrency: 2,
  request_concurrency: 4,
  component: { ready: true },
};
const models = [
  {
    model: "gpt-6-luna",
    supportedReasoningEfforts: [{ reasoningEffort: "low" }],
  },
];
const papers = [
  {
    id: "a",
    revision: 1,
    title: "Alpha paper",
    authors: "Chen",
    source_version: "va",
    source_path: "a.pdf",
  },
  {
    id: "b",
    revision: 1,
    title: "Beta paper",
    authors: "Wang",
    source_version: "vb",
    source_path: "b.pdf",
  },
  {
    id: "c",
    revision: 1,
    title: "Completed paper",
    source_version: "vc",
    source_path: "c.pdf",
  },
];
function mockApi(
  batch: (body: any) => any = (body) => ({
    data: body.papers.map((p: any) => ({
      paper_id: p.paper_id,
      outcome: "queued",
    })),
  }),
) {
  vi.mocked(api).mockImplementation(async (path, body) => {
    if (path === "translation/settings")
      return body ? { ...profile, ...body } : profile;
    if (path === "coach/status") return { models };
    if (path === "translation/jobs")
      return {
        data: [],
        papers: {
          c: { id: "jc", state: "running", current: true, pdf_ready: true },
        },
      };
    if (path === "translation/batch") return batch(body);
    return {};
  });
}
it("searches authors and selects papers across searches without queueing a ready PDF", async () => {
  mockApi();
  const update = vi.fn(),
    read = vi.fn();
  render(
    <TranslationLibrary papers={papers} onUpdate={update} onRead={read} />,
  );
  await screen.findByLabelText("同时翻译论文");
  expect(screen.getByLabelText("翻译 Completed paper")).toHaveProperty(
    "disabled",
    true,
  );
  expect(screen.getByText("双语")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("搜索待翻译论文"), {
    target: { value: "Chen" },
  });
  fireEvent.click(screen.getByLabelText("翻译 Alpha paper"));
  fireEvent.change(screen.getByLabelText("搜索待翻译论文"), {
    target: { value: "Beta" },
  });
  fireEvent.click(screen.getByText("勾选搜索结果"));
  fireEvent.click(screen.getByText("加入后台翻译"));
  await screen.findByText(/已加入 2 篇/);
  const sent = vi
    .mocked(api)
    .mock.calls.find(([path]) => path === "translation/batch")![1];
  expect(sent.papers).toEqual([
    { paper_id: "a", source_version: "va" },
    { paper_id: "b", source_version: "vb" },
  ]);
  expect(update).toHaveBeenCalledOnce();
  fireEvent.change(screen.getByLabelText("搜索待翻译论文"), {
    target: { value: "" },
  });
  fireEvent.click(screen.getByText("阅读双语"));
  expect(read).toHaveBeenCalledWith("c");
});
it("saves concurrency separately and retains a batch request across failed responses and remount", async () => {
  mockApi(() => {
    throw new Error("Disconnected");
  });
  let panel = render(<TranslationLibrary papers={papers} />);
  await screen.findByLabelText("模型请求并发");
  fireEvent.change(screen.getByLabelText("同时翻译论文"), {
    target: { value: "3" },
  });
  await waitFor(() =>
    expect(screen.getByLabelText("同时翻译论文")).toHaveProperty("value", "3"),
  );
  const settings = vi
    .mocked(api)
    .mock.calls.find(
      ([path, body]) => path === "translation/settings" && body,
    )![1];
  expect(settings.paper_concurrency).toBe(3);
  expect(settings.request_concurrency).toBe(4);
  fireEvent.click(screen.getByLabelText("翻译 Alpha paper"));
  fireEvent.click(screen.getByText("加入后台翻译"));
  await screen.findByRole("alert");
  panel.unmount();
  panel = render(<TranslationLibrary papers={papers} />);
  await screen.findByLabelText("批量翻译模型");
  fireEvent.click(screen.getByLabelText("翻译 Alpha paper"));
  fireEvent.click(screen.getByText("加入后台翻译"));
  await screen.findByRole("alert");
  const requests = vi
    .mocked(api)
    .mock.calls.filter(([path]) => path === "translation/batch");
  expect(requests).toHaveLength(2);
  expect(requests[0][1].operation_id).toBe(requests[1][1].operation_id);
});
it("offers bilingual reading while sentence alignment is still running and ignores stale badges", async () => {
  mockApi();
  render(
    <TranslationTools
      paper={papers[0]}
      job={{
        id: "ja",
        state: "running",
        pdf_ready: true,
        stage: "对应句子",
        model: "gpt-6-luna",
      }}
      reload={vi.fn()}
      open
    />,
  );
  await screen.findByText("下载双语 PDF");
  expect(screen.getByText("下载双语 PDF")).toBeTruthy();
  expect(screen.getByText("停止翻译")).toBeTruthy();
  cleanup();
  render(<TranslationBadge job={{ state: "completed", current: false }} />);
  expect(screen.queryByText("双语")).toBeNull();
});

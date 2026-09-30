import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import Coach from "../src/Coach";
import { api, ApiError } from "../src/api";
vi.mock("../src/api", async (original) => ({
  ...(await original<any>()),
  api: vi.fn(),
}));
const paper = {
  id: "p",
  revision: 1,
  source_version: "version",
  page_count: 2,
};
const snapshot = {
  conversation_id: "c",
  conversations: [{ id: "c", title: "带读", created_at: "2026-09-30" }],
  messages: [],
  busy: false,
};
const status = {
  state: "ready",
  skill_loaded: true,
  message: "已连接本机 CLI",
  model: "configured-model",
  models: [],
};
const context = {
  notes: [],
  pending_thoughts: [],
  session: [{ id: "s", revision: 1, note_consent: false }],
};
function view(props: any = {}) {
  return render(
    <Coach
      paper={paper}
      context={context}
      page={1}
      anchor={null}
      onClearAnchor={vi.fn()}
      onLocate={vi.fn()}
      onAction={vi.fn()}
      refresh={vi.fn()}
      report={vi.fn()}
      {...props}
    />,
  );
}
beforeEach(() => {
  vi.stubGlobal(
    "EventSource",
    class {
      close() {}
    },
  );
  vi.mocked(api).mockImplementation(async (path) => {
    if (path === "coach/status") return status;
    if (path.startsWith("coach/conversation/")) return snapshot;
    if (path.startsWith("coach/send/")) return { conversation_id: "c" };
    return {};
  });
});
afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

it("starts the paper route without a prompt and treats written responses separately from detours", async () => {
  view();
  await screen.findByText("已连接本机 CLI");
  fireEvent.click(screen.getByRole("button", { name: "开始跟读", exact: true }));
  await waitFor(() => expect(vi.mocked(api).mock.calls.some(([p]) => p === "coach/send/p")).toBe(true));
  const first = vi.mocked(api).mock.calls.find(([p]) => p === "coach/send/p")![1];
  expect(first.intent).toBe("follow");
  expect(first.content).toBe("");
  expect(first.anchor).toBeNull();
  await waitFor(() => expect(screen.getByRole("button", { name: "开始跟读", exact: true }).hasAttribute("disabled")).toBe(false));
  fireEvent.change(screen.getByLabelText("发给论文教练的消息"), { target: { value: "我认为需要先匹配信息预算。" } });
  fireEvent.click(screen.getByRole("button", { name: "回答并继续主线", exact: true }));
  await waitFor(() => expect(vi.mocked(api).mock.calls.filter(([p]) => p === "coach/send/p")).toHaveLength(2));
  const second = vi.mocked(api).mock.calls.filter(([p]) => p === "coach/send/p")[1][1];
  expect(second.intent).toBe("answer");
  expect(second.content).toBe("我认为需要先匹配信息预算。");
});

it("sends exact words, current paper/page/selection and existing conversation", async () => {
  const anchor = {
    paper_id: "p",
    source_version: "version",
    page_index: 1,
    quote: "selected words",
    rects: [],
    status: "verified",
  };
  view({ anchor });
  await screen.findByText("已连接本机 CLI");
  const input = screen.getByLabelText("发给论文教练的消息");
  fireEvent.change(input, { target: { value: "  我怀疑\n预算没匹配。  " } });
  fireEvent.click(screen.getByLabelText("发送给论文教练"));
  await waitFor(() =>
    expect(
      vi.mocked(api).mock.calls.some(([path]) => path === "coach/send/p"),
    ).toBe(true),
  );
  const [, body] = vi
    .mocked(api)
    .mock.calls.find(([path]) => path === "coach/send/p")!;
  expect(body.content).toBe("  我怀疑\n预算没匹配。  ");
  expect(body.anchor).toEqual(anchor);
  expect(body.page_index).toBe(1);
  expect(body.conversation_id).toBe("c");
  expect(body.model).toBe("");
  await waitFor(() => expect((input as HTMLTextAreaElement).value).toBe(""));
});

it("preserves drafts across navigation and keeps each paper separate", async () => {
  const first = view();
  fireEvent.change(screen.getByLabelText("发给论文教练的消息"), {
    target: { value: "未发送的直觉" },
  });
  first.unmount();
  const other = view({ paper: { ...paper, id: "other" } });
  expect(
    (screen.getByLabelText("发给论文教练的消息") as HTMLTextAreaElement).value,
  ).toBe("");
  other.unmount();
  view();
  expect(
    (screen.getByLabelText("发给论文教练的消息") as HTMLTextAreaElement).value,
  ).toBe("未发送的直觉");
});

it("reconciles an unknown send outcome with the exact same operation", async () => {
  let count = 0;
  vi.mocked(api).mockImplementation(async (path) => {
    if (path === "coach/status") return status;
    if (path.startsWith("coach/conversation/")) return snapshot;
    if (path === "coach/send/p") {
      if (!count++) throw new ApiError("connection lost", 503);
      return { conversation_id: "c" };
    }
    return {};
  });
  view();
  await screen.findByText("已连接本机 CLI");
  fireEvent.change(screen.getByLabelText("发给论文教练的消息"), {
    target: { value: "我的问题" },
  });
  fireEvent.click(screen.getByLabelText("发送给论文教练"));
  await screen.findByRole("alert");
  const before = JSON.parse(localStorage.getItem("prc-chat-send-p")!);
  fireEvent.change(screen.getByLabelText("发给论文教练的消息"), {
    target: { value: "后续草稿" },
  });
  fireEvent.click(screen.getByText("确认上次发送 · 使用相同编号恢复"));
  await waitFor(() =>
    expect(
      vi.mocked(api).mock.calls.filter(([path]) => path === "coach/send/p"),
    ).toHaveLength(2),
  );
  const sent = vi
    .mocked(api)
    .mock.calls.filter(([path]) => path === "coach/send/p");
  expect(sent[0][1]).toEqual(before);
  expect(sent[1][1]).toEqual(before);
  expect(
    (screen.getByLabelText("发给论文教练的消息") as HTMLTextAreaElement).value,
  ).toBe("后续草稿");
});

it("restores saved replies, renders mathematics, and navigates a saved action", async () => {
  const onAction = vi.fn();
  const saved = {
    ...snapshot,
    messages: [
      {
        id: "answer",
        role: "assistant",
        status: "completed",
        content: "**判断**：\\(x^2\\)\n\n<script>unsafe()</script>",
        actions: [{ kind: "idea", id: "idea", label: "已保存研究想法" }],
      },
    ],
  };
  vi.mocked(api).mockImplementation(async (path) =>
    path === "coach/status" ? status : saved,
  );
  const rendered = view({ onAction });
  await screen.findByText("判断");
  expect(rendered.container.querySelector(".katex")).toBeTruthy();
  expect(rendered.container.querySelector("script")).toBeNull();
  fireEvent.click(screen.getByText("已保存研究想法"));
  expect(onAction).toHaveBeenCalledWith("idea");
});

it("creates and reuses only conversations of the selected paper", async () => {
  const second = {
    id: "second",
    title: "阅读对话 2",
    created_at: "2026-09-30",
  };
  vi.mocked(api).mockImplementation(async (path) => {
    if (path === "coach/status") return status;
    if (path === "coach/connect/p") return second;
    if (path === "coach/conversation/p?conversation_id=second")
      return {
        ...snapshot,
        conversation_id: "second",
        conversations: [...snapshot.conversations, second],
      };
    if (path.startsWith("coach/conversation/")) return snapshot;
    return {};
  });
  view();
  await waitFor(() => expect((screen.getByLabelText("当前阅读对话") as HTMLSelectElement).value).toBe("c"));
  expect(screen.queryByText("接入 CLI 对话")).toBeNull();
  fireEvent.click(screen.getByLabelText("新建阅读对话"));
  await waitFor(() =>
    expect(
      (screen.getByLabelText("当前阅读对话") as HTMLSelectElement).value,
    ).toBe("second"),
  );
  expect(vi.mocked(api)).toHaveBeenCalledWith("coach/connect/p", { new: true });
  fireEvent.change(screen.getByLabelText("当前阅读对话"), {
    target: { value: "c" },
  });
  await waitFor(() =>
    expect(
      (screen.getByLabelText("当前阅读对话") as HTMLSelectElement).value,
    ).toBe("c"),
  );
  expect(vi.mocked(api)).toHaveBeenCalledWith("coach/active", {
    paper_id: "p",
    conversation_id: "c",
  });
  expect(
    vi
      .mocked(api)
      .mock.calls.some(([path]) => path.startsWith("coach/threads")),
  ).toBe(false);
});

import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
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
  canonical_conversation_id: "c",
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

it("records learning consent separately and shows source-bound feedback without a mastery score", async () => {
  const locate = vi.fn();
  const observation = {
    conversation_id: "c",
    answer_quote: "还需要预算相同的对照",
    assistance: "prompt-only",
    judgment: "partial",
    criterion: "需要核对实际预算匹配实验",
    feedback: "下一步检查图中的训练预算",
    anchor: {
      paper_id: "p",
      source_version: "version",
      page_index: 0,
      status: "verified",
    },
  };
  view({
    onLocate: locate,
    context: {
      ...context,
      session: [
        {
          ...context.session[0],
          learning_consent: false,
          support_evidence: { evidence: observation },
        },
      ],
    },
  });
  await screen.findByText("已连接本机 CLI");
  fireEvent.click(screen.getByText("本次学习表现 · 1 项"));
  expect(screen.getByText("还需要预算相同的对照")).toBeTruthy();
  fireEvent.click(screen.getByText("核对原文证据"));
  expect(locate).toHaveBeenCalledWith(observation.anchor);
  fireEvent.click(screen.getByText("阅读设置与连接"));
  fireEvent.click(
    screen.getByLabelText("记录实际回答与学习反馈，帮助下次调整讲解"),
  );
  await waitFor(() =>
    expect(
      vi
        .mocked(api)
        .mock.calls.some(
          ([path, body]) =>
            path === "commit" &&
            body.mutations[0].data.learning_consent === true &&
            body.mutations[0].data.note_consent === false,
        ),
    ).toBe(true),
  );
});

it("starts the paper route without a prompt and treats written responses separately from detours", async () => {
  view();
  await screen.findByText("已连接本机 CLI");
  fireEvent.click(
    screen.getByRole("button", { name: "开始跟读", exact: true }),
  );
  await waitFor(() =>
    expect(vi.mocked(api).mock.calls.some(([p]) => p === "coach/send/p")).toBe(
      true,
    ),
  );
  const first = vi
    .mocked(api)
    .mock.calls.find(([p]) => p === "coach/send/p")![1];
  expect(first.intent).toBe("follow");
  expect(first.content).toBe("");
  expect(first.anchor).toBeNull();
  await waitFor(() =>
    expect(
      screen
        .getByRole("button", { name: "开始跟读", exact: true })
        .hasAttribute("disabled"),
    ).toBe(false),
  );
  fireEvent.change(screen.getByLabelText("发给论文教练的消息"), {
    target: { value: "我认为需要先匹配信息预算。" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "回答并继续主线", exact: true }),
  );
  await waitFor(() =>
    expect(
      vi.mocked(api).mock.calls.filter(([p]) => p === "coach/send/p"),
    ).toHaveLength(2),
  );
  const second = vi
    .mocked(api)
    .mock.calls.filter(([p]) => p === "coach/send/p")[1][1];
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

it("keeps one canonical conversation and offers old conversations as read-only history", async () => {
  const old = { id: "old", title: "以前的讨论", created_at: "2026-09-29" };
  vi.mocked(api).mockImplementation(async (path) => {
    if (path === "coach/status") return status;
    if (path.startsWith("coach/conversation/"))
      return {
        ...snapshot,
        conversations: [...snapshot.conversations, old],
        ...(path.endsWith("=old")
          ? { conversation_id: "old", read_only: true }
          : {}),
      };
    return {};
  });
  view();
  await waitFor(() =>
    expect(
      (screen.getByLabelText("当前阅读对话") as HTMLSelectElement).value,
    ).toBe("c"),
  );
  expect(screen.queryByLabelText("新建阅读对话")).toBeNull();
  fireEvent.change(screen.getByLabelText("当前阅读对话"), {
    target: { value: "old" },
  });
  await screen.findByText("历史对话为只读 · 返回当前对话");
  expect(
    (screen.getByLabelText("发给论文教练的消息") as HTMLTextAreaElement)
      .disabled,
  ).toBe(true);
  expect(
    vi
      .mocked(api)
      .mock.calls.some(
        ([path, body]) =>
          path === "coach/active" && body?.conversation_id === "old",
      ),
  ).toBe(false);
  fireEvent.click(screen.getByText("历史对话为只读 · 返回当前对话"));
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
      .mock.calls.some(
        ([path]) =>
          path.startsWith("coach/connect") || path.startsWith("coach/threads"),
      ),
  ).toBe(false);
});

function activeFlow() {
  const flow = {
    status: "active",
    pending_question: "哪项对照能排除预算混杂？",
    source_version: "version",
    current: "evidence",
    completed: [],
    steps: [],
    label: "证据核查",
  };
  vi.mocked(api).mockImplementation(async (path) => {
    if (path === "coach/status") return status;
    if (path.startsWith("coach/conversation/"))
      return { ...snapshot, reading_flow: flow };
    if (path.startsWith("coach/send/")) return { conversation_id: "c" };
    return {};
  });
}
const sentBodies = () =>
  vi
    .mocked(api)
    .mock.calls.filter(([p]) => p === "coach/send/p")
    .map(([, b]) => b);

it("the ordinary send button answers a pending question without any manual intent or help setting", async () => {
  activeFlow();
  view();
  await screen.findByText(/哪项对照能排除预算混杂？/);
  expect(screen.queryByLabelText("帮助方式")).toBeNull();
  expect(screen.queryByLabelText("本轮意图")).toBeNull();
  expect(screen.getByText("Enter 发送，作为对待答问题的回答")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("发给论文教练的消息"), {
    target: { value: "  需要匹配预算  " },
  });
  fireEvent.click(screen.getByLabelText("发送给论文教练"));
  await waitFor(() => expect(sentBodies()).toHaveLength(1));
  expect(sentBodies()[0]).toMatchObject({
    intent: "answer",
    help_mode: "guided",
    content: "  需要匹配预算  ",
  });
});

it("questions about a selection are detours that never advance the pending mainline", async () => {
  activeFlow();
  const anchor = {
    paper_id: "p",
    source_version: "version",
    page_index: 1,
    status: "verified",
    quote: "oracle",
    rects: [],
  };
  view({ anchor });
  await screen.findByText("已附上选中文字");
  expect(screen.queryByText(/哪项对照能排除预算混杂？/)).toBeNull();
  expect(screen.getByText("Enter 发送 · 插话，主线停在第 1 步")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("发给论文教练的消息"), {
    target: { value: "先解释一下 oracle" },
  });
  fireEvent.click(screen.getByLabelText("发送给论文教练"));
  await waitFor(() => expect(sentBodies()).toHaveLength(1));
  expect(sentBodies()[0].intent).toBe("detour");
  fireEvent.click(screen.getByRole("button", { name: "直接讲这处" }));
  await waitFor(() => expect(sentBodies()).toHaveLength(2));
  expect(sentBodies()[1].intent).toBe("detour");
});

it("binds text to the selected page, disables a different page image and consumes only the submitted selection", async () => {
  const anchor = {
    paper_id: "p",
    source_version: "version",
    page_index: 0,
    status: "verified",
    quote: "page zero",
    rects: [],
  };
  const clear = vi.fn();
  view({ anchor, onClearAnchor: clear });
  await screen.findByText("已连接本机 CLI");
  expect(screen.queryByRole("checkbox", { name: /整页图像/ })).toBeNull();
  fireEvent.change(screen.getByLabelText("发给论文教练的消息"), {
    target: { value: "解释这一句" },
  });
  fireEvent.click(screen.getByLabelText("发送给论文教练"));
  await waitFor(() => expect(clear).toHaveBeenCalledTimes(1));
  expect(sentBodies()[0]).toMatchObject({
    page_index: 0,
    anchor,
    page_image: "",
    intent: "detour",
  });
});

it("preserves a newer selection while a send is in flight", async () => {
  let finish!: (v: any) => void;
  vi.mocked(api).mockImplementation(async (path) => {
    if (path === "coach/status") return status;
    if (path.startsWith("coach/conversation/")) return snapshot;
    if (path === "coach/send/p")
      return new Promise((r) => {
        finish = r;
      });
    return {};
  });
  const anchor = {
    paper_id: "p",
    source_version: "version",
    page_index: 1,
    quote: "first",
    rects: [],
    status: "verified",
  };
  const clear = vi.fn();
  const mounted = view({ anchor, onClearAnchor: clear });
  await screen.findByText("已连接本机 CLI");
  fireEvent.change(screen.getByLabelText("发给论文教练的消息"), {
    target: { value: "first question" },
  });
  fireEvent.click(screen.getByLabelText("发送给论文教练"));
  await waitFor(() => expect(finish).toBeDefined());
  mounted.rerender(
    <Coach
      paper={paper}
      context={context}
      page={1}
      anchor={{ ...anchor, quote: "newer" }}
      onClearAnchor={clear}
      onLocate={vi.fn()}
      onAction={vi.fn()}
      refresh={vi.fn()}
      report={vi.fn()}
    />,
  );
  await act(async () => finish({ conversation_id: "c" }));
  expect(clear).not.toHaveBeenCalled();
});

it("does not send while an IME is composing, including keyCode 229 fallback", async () => {
  view();
  await screen.findByText("已连接本机 CLI");
  const input = screen.getByLabelText("发给论文教练的消息");
  fireEvent.change(input, { target: { value: "输入中文" } });
  fireEvent.keyDown(input, { key: "Enter", isComposing: true });
  fireEvent.keyDown(input, { key: "Enter", ctrlKey: true, isComposing: true });
  fireEvent.keyDown(input, { key: "Enter", metaKey: true, keyCode: 229 });
  fireEvent.keyDown(input, { key: "Enter", shiftKey: true });
  expect(sentBodies()).toHaveLength(0);
  fireEvent.keyDown(input, { key: "Enter" });
  await waitFor(() => expect(sentBodies()).toHaveLength(1));
});

it("renders CJK bold after full-width punctuation and keeps the quoted source with my words", async () => {
  const anchor = {
    paper_id: "p",
    source_version: "version",
    page_index: 0,
    quote: "Both policies receive 20 observations.",
    status: "verified",
  };
  vi.mocked(api).mockImplementation(async (path) => {
    if (path === "coach/status") return status;
    if (path.startsWith("coach/conversation/"))
      return {
        ...snapshot,
        messages: [
          {
            id: "u",
            role: "user",
            content: "会不会只是测量更多？",
            status: "completed",
            anchor,
          },
          {
            id: "a",
            role: "assistant",
            content: "**你来判断：**还缺什么证据？",
            status: "completed",
            anchor,
          },
        ],
      };
    return {};
  });
  view();
  const bold = await screen.findByText("你来判断：");
  expect(bold.tagName).toBe("STRONG");
  expect(
    screen.getByText("Both policies receive 20 observations."),
  ).toBeTruthy();
  // The reply shares the question's location, so it is shown once, and
  // completed turns are not labelled with a redundant saved status.
  expect(
    document.querySelectorAll(".coach-messages .anchor-label"),
  ).toHaveLength(1);
  expect(screen.queryByText("已保存")).toBeNull();
});

it("explains an unavailable coach instead of showing a perpetual connecting state", async () => {
  const offline = {
    state: "unavailable",
    message: "CLI 连接暂不可用",
    models: [],
  };
  let current: any = offline;
  vi.mocked(api).mockImplementation(async (path) => {
    if (path === "coach/status") return current;
    if (path === "coach/reconnect") return (current = status);
    if (path.startsWith("coach/conversation/")) return snapshot;
    return {};
  });
  view();
  const notice = await screen.findByRole("status");
  expect(notice.textContent).toContain("AI 带读暂未连接");
  expect(screen.getByText("未连接")).toBeTruthy();
  expect(screen.queryByText("连接中")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "重新连接" }));
  await waitFor(() => expect(screen.queryByRole("status")).toBeNull());
  expect(api).toHaveBeenCalledWith("coach/reconnect", {});
  expect(screen.getByText("已连接")).toBeTruthy();
});

it("keeps the mainline step, its button and the pending question in the panel when a tools drawer exists", async () => {
  const drawer = document.createElement("section");
  document.body.append(drawer);
  const steps = ["orient", "insight", "model", "method", "evidence", "synthesis", "transfer", "recall"].map(
    (id) => ({ id, label: id === "model" ? "问题设定" : id }),
  );
  vi.mocked(api).mockImplementation(async (path) => {
    if (path === "coach/status") return status;
    if (path.startsWith("coach/conversation/"))
      return {
        ...snapshot,
        reading_flow: {
          status: "active",
          current: "model",
          label: "问题设定",
          goal: "核对输入、输出、可用信息、假设与代价。",
          steps,
          completed: [{ step: "orient" }, { step: "insight" }],
          pending_question: "决策时真正可用的信息是什么？",
        },
      };
    return {};
  });
  const { container } = view({ toolsContainer: drawer, onOpenTools: vi.fn() });
  await screen.findByText("第 3/8 步 · 问题设定");
  const panel = container.querySelector(".coach-panel")!;
  const strip = screen.getByRole("button", { name: /第 3 章 · 问题设定/ });
  expect(panel.contains(strip)).toBe(true);
  expect(strip.textContent).toContain("决策时真正可用的信息是什么？");
  fireEvent.click(strip);
  const task = screen.getByRole("region", { name: "本轮任务" });
  expect(within(task).getByRole("button", { name: "回答" })).toBeTruthy();
  expect(drawer.querySelector(".coach-mainline")).toBeNull();
  expect(panel.querySelectorAll(".coach-progress-track li.done")).toHaveLength(2);
  expect(screen.queryByText("问题设定", { selector: ".coach-route li" })).toBeNull();
  fireEvent.click(screen.getByTitle("查看八步路线与核查依据"));
  expect(screen.getByLabelText("八步阅读路线")).toBeTruthy();
  drawer.remove();
});

// ---- branch explainer inside the coach ----
function explainerMocks(initialMessages: any[]) {
  const stream: { emit?: (s: any) => void } = {};
  vi.stubGlobal(
    "EventSource",
    class {
      onmessage: any;
      onopen: any;
      constructor(url: string) {
        // The coach's own stream is the first one opened; the panel opens its own later.
        if (!stream.emit) stream.emit = (s) => this.onmessage?.({ data: JSON.stringify(s) });
      }
      close() {}
    },
  );
  const record = {
    id: "x1", paper_id: "p", branch_id: "x1", seq: 1, title: "预算为什么要相同", question: "为什么要匹配预算？",
    doc: { title: "预算为什么要相同", subtitle: "", lang: "zh", lead: [{ type: "md", text: "先说结论。", line: 1 }], panels: [] },
    warnings: [], anchor: null, created_at: "t", updated_at: "t",
    return_point: { status: "active", step: "model", label: "问题设定", pending_question: "", next_action: "" },
  };
  vi.mocked(api).mockImplementation(async (path: string) => {
    if (path === "coach/status") return status;
    if (path.startsWith("coach/conversation/")) return { ...snapshot, messages: initialMessages };
    if (path === "coach/explainers/p") return { data: [{ ...record, doc: undefined }] };
    if (path === "coach/explainer/x1") return record;
    return {};
  });
  return { stream };
}
const withExplainer = (id = "x1") => ({
  id: "m" + id, role: "assistant", content: "我在讲解面板里画了图。", status: "completed", intent: "detour",
  actions: [{ kind: "explainer", id, branch_id: id, label: "讲解 · 预算为什么要相同", rev: "t" }],
});

it("keeps old explainer pages folded on reload; one click opens the page in the conversation", async () => {
  explainerMocks([withExplainer()]);
  view();
  const toggle = await screen.findByRole("button", { name: /支线.*预算为什么要相同/ });
  expect(toggle.getAttribute("aria-expanded")).toBe("false");
  expect(screen.queryByRole("dialog", { name: "讲解面板" })).toBeNull();
  fireEvent.click(toggle);
  expect(await screen.findByText("先说结论。")).toBeTruthy();
  // The side panel is still one click away.
  fireEvent.click(screen.getByRole("button", { name: "放大到侧边" }));
  expect(await screen.findByRole("dialog", { name: "讲解面板" })).toBeTruthy();
});

it("opens a new explainer page inside the conversation, and a follow-up stays in the same branch", async () => {
  const { stream } = explainerMocks([]);
  view();
  await screen.findByText("已连接本机 CLI");
  await waitFor(() => expect(stream.emit).toBeTruthy());
  await act(async () => {
    stream.emit!({ ...snapshot, messages: [withExplainer()] });
  });
  const toggle = await screen.findByRole("button", { name: /支线.*预算为什么要相同/ });
  await waitFor(() => expect(toggle.getAttribute("aria-expanded")).toBe("true"));
  expect(screen.queryByRole("dialog", { name: "讲解面板" })).toBeNull(); // nothing covers the paper
  fireEvent.change(screen.getByLabelText("接着问这一页"), { target: { value: "那误差条呢？" } });
  fireEvent.click(screen.getByRole("button", { name: "发送追问" }));
  await waitFor(() =>
    expect(vi.mocked(api)).toHaveBeenCalledWith("coach/send/p", expect.objectContaining({ content: "那误差条呢？", intent: "detour", branch_id: "x1" })),
  );
});

it("closes a side quest with the reader's own sentence, and the quest log files it under its chapter", async () => {
  explainerMocks([withExplainer()]);
  const base = vi.mocked(api).getMockImplementation()!;
  let quest: any = undefined;
  vi.mocked(api).mockImplementation(async (path: string, body?: any) => {
    if (path === "coach/branch/x1/quest") {
      quest = { status: body.status, takeaway: body.takeaway.trim(), closed_at: "t2" };
      return { branch_id: "x1", quest };
    }
    if (path === "coach/explainers/p") {
      const [first] = (await base(path)).data;
      return { data: [{ ...first, gist: "先说结论。", quest }] };
    }
    if (path.startsWith("coach/conversation/"))
      return { ...(await base(path)), reading_flow: {
        status: "active", current: "model", label: "问题设定",
        steps: [{ id: "orient", label: "定位" }, { id: "model", label: "问题设定" }],
        completed: [{ step: "orient", page_index: 0, takeaway: "这篇在比两种观测策略。" }],
        pending_question: "", choices: [],
      } };
    return base(path, body);
  });
  view();
  fireEvent.click(await screen.findByRole("button", { name: /支线.*预算为什么要相同/ }));
  const box = await screen.findByRole("group", { name: "支线任务" });
  fireEvent.click(within(box).getByRole("button", { name: /我弄懂了/ }));
  const mine = "  预算不同，所以不能直接比  ";
  fireEvent.change(within(box).getByLabelText(/用一句话写下/), { target: { value: mine } });
  fireEvent.click(within(box).getByRole("button", { name: /记下，支线完成/ }));
  await waitFor(() => expect(vi.mocked(api)).toHaveBeenCalledWith("coach/branch/x1/quest", { status: "done", takeaway: mine }));
  expect(await screen.findByText(/支线完成：已弄懂/)).toBeTruthy();
  expect(screen.getByText("已弄懂", { selector: ".xp-card-status" })).toBeTruthy();

  fireEvent.click(screen.getByRole("button", { name: /任务日志/ }));
  const log = await screen.findByRole("dialog", { name: "任务日志" });
  expect(within(log).getByText(/主线 1\/2 章 · 支线 1 条（弄懂 1）/)).toBeTruthy();
  const chapter = within(log).getByRole("list", { name: "第 2 章的支线" });
  expect(within(chapter).getByText("我的收获：" + mine.trim())).toBeTruthy();
  expect(within(log).getByText("收获：这篇在比两种观测策略。")).toBeTruthy();
  expect(within(log).queryByText(/分|XP|掌握度/)).toBeNull();
  // A side quest in the log opens its page in the conversation.
  fireEvent.click(within(chapter).getByRole("button", { name: /预算为什么要相同/ }));
  expect(screen.queryByRole("dialog", { name: "任务日志" })).toBeNull();
});

it("parks a side quest without calling it a failure", async () => {
  explainerMocks([withExplainer()]);
  const base = vi.mocked(api).getMockImplementation()!;
  vi.mocked(api).mockImplementation(async (path: string, body?: any) =>
    path === "coach/branch/x1/quest" ? { branch_id: "x1", quest: { status: body.status, takeaway: "", closed_at: "t" } } : base(path, body));
  view();
  fireEvent.click(await screen.findByRole("button", { name: /支线.*预算为什么要相同/ }));
  fireEvent.click(within(await screen.findByRole("group", { name: "支线任务" })).getByRole("button", { name: /先放一放/ }));
  expect(await screen.findByText("这条支线先放一放")).toBeTruthy();
  expect(screen.getByRole("button", { name: "继续这条支线" })).toBeTruthy();
});

// ---- the coach points at sentences in the PDF ----
const focus = (id: string, page = 2) => ({
  kind: "focus", id, label: `第 ${page + 1} 页 · 作者的主张`, rev: "t",
  anchor: { paper_id: "p", source_version: "version", page_index: page, status: "verified", quote: "We show", rects: [[1, 2, 3, 4]] },
  marks: [{ n: 1, quote: "We show", rects: [[1, 2, 3, 4]] }],
});
const pointing = (mid: string, actions: any[]) => ({ id: mid, role: "assistant", content: "看①。", status: "completed", intent: "follow", actions });

it("shows old marks on load without moving the PDF, then jumps once per new coach reply", async () => {
  const { stream } = explainerMocks([pointing("m0", [focus("f0", 1)])]);
  const onFocus = vi.fn();
  view({ onFocus });
  await waitFor(() => expect(onFocus).toHaveBeenCalledWith(expect.objectContaining({ id: "f0" }), "restore"));
  await waitFor(() => expect(stream.emit).toBeTruthy());
  await act(async () => {
    stream.emit!({ ...snapshot, messages: [pointing("m0", [focus("f0", 1)]), pointing("m1", [focus("f1")])] });
  });
  expect(onFocus).toHaveBeenLastCalledWith(expect.objectContaining({ id: "f1" }), "auto");
  // A second place in the same reply waits for a click.
  await act(async () => {
    stream.emit!({ ...snapshot, messages: [pointing("m0", [focus("f0", 1)]), pointing("m1", [focus("f1"), focus("f2", 0)])] });
  });
  expect(onFocus.mock.calls.filter(([, how]) => how === "auto")).toHaveLength(1);
  fireEvent.click(screen.getByRole("button", { name: "第 1 页 · 作者的主张" }));
  expect(onFocus).toHaveBeenLastCalledWith(expect.objectContaining({ id: "f2" }), "click");
});

it("turns the pending question into a task with one-tap answers, a hint, and an inline mainline figure", async () => {
  const steps = ["orient", "insight", "model", "method", "evidence", "synthesis", "transfer", "recall"].map((id) => ({ id, label: id }));
  const flow = {
    status: "active", current: "evidence", label: "证据核查", goal: "g", steps, completed: [],
    pending_question: "预算相同后，你预测差距会怎样？", choices: ["几乎消失", "仍然明显"], check: "先预测，再对照真实图表。",
  };
  const figure = { id: "fig", branch_id: "fig", kind: "explainer", mainline: true, label: "图解 · 预算对比", rev: "t" };
  const messages = [{ id: "m1", role: "assistant", content: "先预测。", status: "completed", intent: "follow",
    actions: [figure, focus("f1", 1)] }];
  vi.mocked(api).mockImplementation(async (path: string) => {
    if (path === "coach/status") return status;
    if (path.startsWith("coach/conversation/")) return { ...snapshot, messages, reading_flow: flow };
    if (path === "coach/explainer/fig") return {
      id: "fig", branch_id: "fig", seq: 1, title: "预算对比", question: "", origin: "mainline", warnings: [], anchor: null,
      created_at: "t", updated_at: "t", return_point: null,
      doc: { title: "预算对比", subtitle: "", lang: "zh", lead: [{ type: "md", text: "两组都是 20 次观测。", line: 1 }], panels: [] },
    };
    if (path.startsWith("coach/send/")) return { conversation_id: "c" };
    return {};
  });
  const onFocus = vi.fn();
  view({ onFocus });
  fireEvent.click(await screen.findByRole("button", { name: /第 5 章 · 证据核查/ }));
  const task = await screen.findByRole("region", { name: "本轮任务" });
  expect(within(task).getByText("先预测，再对照真实图表。")).toBeTruthy();
  // The figure is part of the reply, not a button that opens a detour panel.
  expect(await screen.findByRole("figure", { name: "图解：预算对比" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "图解 · 预算对比" })).toBeNull();
  fireEvent.click(within(task).getByRole("button", { name: "第 2 页 · 作者的主张" }));
  expect(onFocus).toHaveBeenLastCalledWith(expect.objectContaining({ id: "f1" }), "click");
  fireEvent.click(within(task).getByRole("button", { name: "几乎消失" }));
  await waitFor(() => expect(vi.mocked(api)).toHaveBeenCalledWith("coach/send/p", expect.objectContaining({ content: "几乎消失", intent: "answer" })));
});

it("an empty Enter continues the mainline only when nothing waits for an answer", async () => {
  const steps = ["orient", "insight", "model", "method", "evidence", "synthesis", "transfer", "recall"].map((id) => ({ id, label: id }));
  vi.mocked(api).mockImplementation(async (path: string) => {
    if (path === "coach/status") return status;
    if (path.startsWith("coach/conversation/"))
      return { ...snapshot, reading_flow: { status: "active", current: "model", label: "问题设定", goal: "g", steps, completed: [], pending_question: "", return_action: "核对输入输出" } };
    if (path.startsWith("coach/send/")) return { conversation_id: "c" };
    return {};
  });
  view();
  const strip = await screen.findByRole("button", { name: /第 3 章 · 问题设定/ });
  expect(strip.textContent).toContain("下一步：核对输入输出");
  await screen.findByText("已连接本机 CLI");
  fireEvent.keyDown(screen.getByLabelText("发给论文教练的消息"), { key: "Enter" });
  await waitFor(() => expect(vi.mocked(api)).toHaveBeenCalledWith("coach/send/p", expect.objectContaining({ intent: "follow" })));
});

it("draws a mainline reply as a quest card: chapter, source cards, clickable marks, task and completion", async () => {
  const steps = ["orient", "insight", "model", "method", "evidence", "synthesis", "transfer", "recall"].map((id, i) => ({ id, label: ["阅读目标", "独特贡献", "问题设定", "方法机制", "证据核查", "边界与判断", "研究启发", "回忆与复习"][i] }));
  const flow = { status: "active", current: "evidence", label: "证据核查", goal: "g", steps, completed: [], pending_question: "你预测差距还在吗？", choices: ["几乎消失", "仍然明显"] };
  const reply = {
    id: "m1", role: "assistant", intent: "follow", step: "evidence", status: "completed",
    content: "预算相同，差距只剩 2。\n\n先看 ①，再回答。",
    actions: [focus("f1", 1)],
    task: { question: "你预测差距还在吗？", choices: ["几乎消失", "仍然明显"] },
    completed_step: { step: "model", label: "问题设定", takeaway: "输入是历史读数。", page_index: 0 },
  };
  vi.mocked(api).mockImplementation(async (path: string) => {
    if (path === "coach/status") return status;
    if (path.startsWith("coach/conversation/")) return { ...snapshot, messages: [reply], reading_flow: flow };
    if (path.startsWith("coach/send/")) return { conversation_id: "c" };
    return {};
  });
  const onFocus = vi.fn();
  view({ onFocus });
  expect(await screen.findByText("主线 · 第 5/8 章")).toBeTruthy();
  fireEvent.click(screen.getByTitle("在 PDF 里看这一句"));
  expect(onFocus).toHaveBeenLastCalledWith(expect.objectContaining({ id: "f1" }), "click");
  onFocus.mockClear();
  fireEvent.click(screen.getByRole("button", { name: "①" }));
  expect(onFocus).toHaveBeenLastCalledWith(expect.objectContaining({ id: "f1" }), "click");
  expect(screen.getByRole("status").textContent).toContain("收获：输入是历史读数。");
  await screen.findByText("已连接本机 CLI");
  fireEvent.click(within(screen.getByRole("group", { name: "快速回答" })).getByRole("button", { name: "仍然明显" }));
  await waitFor(() => expect(vi.mocked(api)).toHaveBeenCalledWith("coach/send/p", expect.objectContaining({ content: "仍然明显", intent: "answer" })));
});

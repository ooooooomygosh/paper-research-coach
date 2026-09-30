import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { App } from "../src/main";
import { api, ApiError } from "../src/api";
vi.mock("react-dom/client", () => ({
  createRoot: () => ({ render: vi.fn() }),
}));
vi.mock("../src/PdfReader", () => ({ default: () => null }));
vi.mock("../src/api", async (original) => ({
  ...(await original<any>()),
  api: vi.fn(),
}));
beforeEach(() => {
  vi.stubGlobal(
    "EventSource",
    class {
      close() {}
    },
  );
});
afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

it("guides a new browser and accepts the complete private launch link", async () => {
  let authenticated = false;
  vi.mocked(api).mockImplementation(async (path, body) => {
    if (path === "login") {
      authenticated = body.token === "test-token";
      return {};
    }
    if (path === "state") {
      if (!authenticated) throw new ApiError("Private address required", 401);
      return { papers: [], sync: {}, conflicts: [] };
    }
    return {};
  });
  render(<App />);
  await screen.findByText("这个浏览器还没有连接你的本机工作台。");
  await waitFor(() => expect(vi.mocked(api)).toHaveBeenCalledWith("state"));
  expect(screen.queryByRole("alert")).toBeNull();
  fireEvent.change(screen.getByLabelText("完整启动链接"), {
    target: { value: window.location.origin + "/#token=test-token" },
  });
  fireEvent.click(screen.getByRole("button", { name: "连接工作台" }));
  await screen.findByText("从一篇值得读的论文开始");
  expect(vi.mocked(api)).toHaveBeenCalledWith("login", { token: "test-token" });
});

it("does not send credentials from a launch link for another origin", async () => {
  vi.mocked(api).mockRejectedValue(new ApiError("Unauthorized", 401));
  render(<App />);
  fireEvent.change(screen.getByLabelText("完整启动链接"), {
    target: { value: "http://other.example/#token=private" },
  });
  fireEvent.click(screen.getByRole("button", { name: "连接工作台" }));
  await screen.findByRole("alert");
  expect(vi.mocked(api).mock.calls.some(([path]) => path === "login")).toBe(
    false,
  );
});
it("forgets a selected paper that belongs to a different local library", async () => {
  localStorage.setItem("prc-selected", "old-library-paper");
  vi.stubGlobal(
    "EventSource",
    class {
      close() {}
    },
  );
  const paper = {
    id: "new-paper",
    revision: 1,
    title: "New library paper",
    source_version: "",
    source_path: "",
    comparison: {},
    status: "queued",
  };
  vi.mocked(api).mockImplementation(async (path) => {
    if (path === "state") return { papers: [paper], sync: {}, conflicts: [] };
    if (path === "context/new-paper")
      return { paper, session: [], notes: [], seq: 1 };
    throw new Error("Missing paper");
  });
  render(<App />);
  expect(
    await screen.findByRole("heading", { name: "New library paper" }),
  ).toBeTruthy();
  await waitFor(() =>
    expect(localStorage.getItem("prc-selected")).toBe("new-paper"),
  );
  expect(
    vi
      .mocked(api)
      .mock.calls.some(([path]) => path === "context/old-library-paper"),
  ).toBe(false);
});

it("keeps the library hidden across reloads and brings it back on demand", async () => {
  vi.mocked(api).mockImplementation(async (path) =>
    path === "state" ? { papers: [], sync: {}, conflicts: [] } : {},
  );
  const first = render(<App />);
  expect(screen.queryByRole("heading", { name: "我的论文" })).toBeNull();
  fireEvent.click(await screen.findByRole("button", { name: "显示论文栏" }));
  fireEvent.click(screen.getByRole("button", { name: "隐藏论文栏" }));
  expect(localStorage.getItem("prc-sidebar-hidden")).toBe("true");
  expect(screen.queryByRole("heading", { name: "我的论文" })).toBeNull();
  first.unmount();
  render(<App />);
  fireEvent.click(await screen.findByRole("button", { name: "显示论文栏" }));
  expect(screen.getByRole("heading", { name: "我的论文" })).toBeTruthy();
  expect(localStorage.getItem("prc-sidebar-hidden")).toBe("false");
});

it("preserves the draft and mounted conversation across immersive mode", async () => {
  const paper = {
    id: "p",
    revision: 1,
    title: "Quiet reading",
    source_version: "v",
    source_path: "source.pdf",
    page_count: 2,
    status: "reading",
  };
  vi.mocked(api).mockImplementation(async (path) => {
    if (path === "state")
      return {
        papers: [paper],
        sync: { collection: "configured" },
        conflicts: [],
      };
    if (path === "context/p")
      return {
        paper,
        session: [
          { id: "s", revision: 1, goal: "Check evidence", stage: "evidence" },
        ],
        notes: [],
        seq: 1,
      };
    if (path === "coach/status")
      return { state: "ready", models: [], message: "Connected" };
    if (path.startsWith("coach/conversation/"))
      return {
        conversation_id: "c",
        canonical_conversation_id: "c",
        conversations: [{ id: "c", title: "阅读" }],
        messages: [],
        busy: false,
      };
    if (path === "translation/p/jobs") return { data: [] };
    if (path === "translation/settings")
      return { model: "gpt-6-luna", effort: "low", component: { ready: true } };
    return {};
  });
  const rendered = render(<App />);
  const input = (await screen.findByLabelText(
    "发给论文教练的消息",
  )) as HTMLTextAreaElement;
  fireEvent.change(input, { target: { value: "An unfinished thought" } });
  expect(screen.queryByRole("combobox", { name: "教练模型" })).toBeNull();
  fireEvent.click(screen.getByLabelText("进入沉浸模式"));
  expect(rendered.container.querySelector(".immersive")).toBeTruthy();
  expect(screen.getByLabelText("发给论文教练的消息")).toBe(input);
  fireEvent.click(screen.getByLabelText("更多阅读工具"));
  fireEvent.click(screen.getByRole("button", { name: "刷新同步" }));
  await waitFor(() =>
    expect(vi.mocked(api)).toHaveBeenCalledWith("sync/refresh", {}),
  );
  fireEvent.keyDown(document, { key: "Escape" });
  expect(rendered.container.querySelector(".immersive")).toBeTruthy();
  fireEvent.keyDown(document, { key: "Escape" });
  expect(rendered.container.querySelector(".immersive")).toBeNull();
  expect(screen.getByLabelText("发给论文教练的消息")).toBe(input);
  expect(input.value).toBe("An unfinished thought");
});

// @vitest-environment jsdom
import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { artifactMessage } from "../src/ArtifactFrame";
import Workspace from "../src/Workspace";
import InteractiveStudio from "../src/InteractiveStudio";
import { unitProgress } from "../src/workspace-api";
import { createStudio, studioPaperContext } from "../src/studio-context";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); localStorage.clear(); });

it("keeps the same unit's notes separate across learning versions", () => {
  const progress = { "v1:u1": { note: "旧版笔记" }, "v2:u1": { note: "新版笔记" } };
  expect(unitProgress(progress, "u1", "v1")?.note).toBe("旧版笔记");
  expect(unitProgress(progress, "u1", "v2")?.note).toBe("新版笔记");
});

it("makes historical explanations read-only before continuing with the current source", async () => {
  const row = { id: "studio-a", title: "讲解", revision: 1, question: "当前问题", source: "## 当前草稿", theme: "paper", template: "doc", language: "zh", context: {},
    published: { version: "current", title: "当前" }, history: [{ version: "previous", title: "历史", created_at: "2026-11-04T01:00:00Z" }] };
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => row })));
  render(<InteractiveStudio id={row.id} jobs={[]} kbs={[]} page={0} reload={vi.fn()} report={vi.fn()} />);
  await screen.findByRole("button", { name: "按要求更新讲解" });
  fireEvent.change(screen.getByLabelText("讲解版本"), { target: { value: "previous" } });
  expect(screen.queryByRole("button", { name: "按要求更新讲解" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "返回当前草稿" }));
  expect(screen.getByRole("button", { name: "按要求更新讲解" })).toBeTruthy();
});

it("accepts only the selected opaque frame's scoped reply and storage messages", () => {
  const frame = {} as Window;
  const data = { channel: "prc-workspace-v1", scope: { type: "kb", id: "kb-a" }, kind: "question", text: "解释这个概念" };
  expect(artifactMessage({ data, source: frame } as MessageEvent, frame, "kb", "kb-a")?.text).toBe(data.text);
  expect(artifactMessage({ data, source: {} } as MessageEvent, frame, "kb", "kb-a")).toBeNull();
  expect(artifactMessage({ data, source: frame } as MessageEvent, frame, "kb", "kb-b")).toBeNull();
  expect(artifactMessage({ data: { ...data, text: "a".repeat(16001) }, source: frame } as MessageEvent, frame, "kb", "kb-a")).toBeNull();
});

it("creating a knowledge base saves local metadata and does not start account analysis", async () => {
  const requests: { path: string; body?: any }[] = [];
  const fetch = vi.fn(async (path: string, options: any) => {
    requests.push({ path, body: options?.body && JSON.parse(options.body) });
    if (path === "/api/workspace") return { ok: true, json: async () => ({ studios: [], kbs: [], jobs: [] }) };
    if (path === "/api/workspace/kbs") return { ok: true, json: async () => ({ id: "kb-created" }) };
    return { ok: true, json: async () => ({ id: "kb-created", title: "资料集", materials: [], history: [], chat: [], progress: {}, depth: "systematic", language: "zh" }) };
  });
  vi.stubGlobal("fetch", fetch);
  render(<Workspace mode="knowledge" page={0} report={vi.fn()} />);
  fireEvent.click(screen.getAllByRole("button", { name: "新建知识库" })[0]);
  fireEvent.change(screen.getByLabelText("知识库名称"), { target: { value: "资料集" } });
  fireEvent.change(screen.getByLabelText("学习深度"), { target: { value: "systematic" } });
  fireEvent.click(screen.getByRole("button", { name: "创建" }));
  await waitFor(() => expect(requests.some(request => request.path === "/api/workspace/kbs")).toBe(true));
  expect(requests.find(request => request.path === "/api/workspace/kbs")?.body).toEqual({ title: "资料集", depth: "systematic" });
  expect(requests.some(request => /build|generate|\/ask/.test(request.path))).toBe(false);
});

it("creates the draft from the selection's physical page without starting the account job", async () => {
  const fetch = vi.fn(async (_path: string, _opts: RequestInit) => ({ ok: true, json: async () => ({ id: "studio-a" }) }));
  vi.stubGlobal("fetch", fetch);
  const paper = { id: "p", source_version: "v2", title: "合成论文", source_path: "fixture.pdf" };
  const anchor = { paper_id: "p", source_version: "v2", page_index: 1, quote: " Exact passage ", status: "verified" };
  const source = studioPaperContext(paper, 3, anchor);
  expect(source).toEqual({ paper_id: "p", source_version: "v2", page_index: 1, quote: "Exact passage" });
  expect(studioPaperContext(paper, 3, { ...anchor, source_version: "v1" })).toEqual({
    paper_id: "p", source_version: "v2", page_index: 3,
  });
  await createStudio(paper, source!);
  expect(fetch).toHaveBeenCalledOnce();
  expect(fetch.mock.calls[0][0]).toBe("/api/workspace/studios");
  expect(JSON.parse(String(fetch.mock.calls[0][1].body))).toEqual({
    title: "合成论文 · 第 2 页", context: source, presentation: "components",
  });
});

it("retains an edited follow-up and the last published page when generation fails", async () => {
  const initial = { id: "s1", revision: 1, title: "讲解", question: "已发送问题", source: "", presentation: "components", context: {},
    published: { version: "v1", title: "上次讲解" }, history: [] };
  let row = initial;
  const fetch = vi.fn(async (_path: string, init: RequestInit) => {
    if (init?.method === "PUT") row = { ...row, ...JSON.parse(String(init.body)), revision: row.revision + 1 };
    return { ok: true, json: async () => row };
  });
  vi.stubGlobal("fetch", fetch);
  const pending = { id: "j1", owner: "s1", state: "running", stage: "生成中" };
  const props = { id: "s1", kbs: [], page: 0, reload: vi.fn(async () => undefined), report: vi.fn() };
  const view = render(<InteractiveStudio {...props} jobs={[pending]} />);
  await screen.findByTitle("上次讲解");
  const input = screen.getByLabelText<HTMLTextAreaElement>("交互式讲解问题");
  fireEvent.change(input, { target: { value: "正在编辑的追问" } });
  view.rerender(<InteractiveStudio {...props} jobs={[{ ...pending, state: "failed", stage: "失败", message: "合成错误" }]} />);
  await screen.findByText("合成错误");
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
  expect(input.value).toBe("正在编辑的追问");
  expect(screen.getByRole("button", { name: "重新生成" })).toBeTruthy();
  expect(screen.getByTitle("上次讲解")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "保存草稿" }));
  await screen.findByText("草稿已保存。");
  expect(row.question).toBe("正在编辑的追问");
  expect(fetch.mock.calls.some(([url]) => url.endsWith("/generate"))).toBe(false);
});

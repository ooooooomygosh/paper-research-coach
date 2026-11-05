// @vitest-environment jsdom
import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { artifactMessage } from "../src/ArtifactFrame";
import Workspace from "../src/Workspace";
import InteractiveStudio from "../src/InteractiveStudio";
import { unitProgress } from "../src/workspace-api";

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

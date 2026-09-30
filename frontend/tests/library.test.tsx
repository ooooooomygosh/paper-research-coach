import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "../src/main";
import { api } from "../src/api";
vi.mock("react-dom/client", () => ({
  createRoot: () => ({ render: vi.fn() }),
}));
vi.mock("../src/PdfReader", () => ({ default: () => null }));
vi.mock("../src/api", async (original) => ({
  ...(await original<any>()),
  api: vi.fn(),
}));
afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.unstubAllGlobals();
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

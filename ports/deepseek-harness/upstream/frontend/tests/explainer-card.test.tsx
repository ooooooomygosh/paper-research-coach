import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import ExplainerCard from "../src/explainer/ExplainerCard";
import { explainerHtml } from "../src/explainer/exportHtml";
import { api } from "../src/api";

vi.mock("../src/api", async (original) => ({ ...(await original<any>()), api: vi.fn() }));
const here = dirname(fileURLToPath(import.meta.url));
const doc = JSON.parse(readFileSync(resolve(here, "../../tests/fixtures/explainers/budget-zh.doc.json"), "utf8"));
const record = { id: "x1", branch_id: "x1", seq: 1, title: doc.title, question: "预算一样吗？", doc, warnings: [], anchor: null,
  created_at: "t", updated_at: "t", return_point: null, paper_id: "p" };
afterEach(() => { cleanup(); vi.clearAllMocks(); });

function card(props: any = {}) {
  vi.mocked(api).mockResolvedValue(record);
  const onAsk = vi.fn(), onToggle = vi.fn();
  const view = render(<ExplainerCard id="x1" branchId="x1" expanded onToggle={onToggle} onAsk={onAsk} {...props} />);
  return { onAsk, onToggle, view };
}

it("draws lettered panel cards and the conclusion first", async () => {
  card();
  const panels = await screen.findAllByRole("region", { name: /^[A-Z] / });
  expect(panels.length).toBe(doc.panels.length);
  expect(panels[0].getAttribute("aria-label")!.startsWith("A ")).toBe(true);
  expect(screen.getByRole("note", { name: "结论" })).toBeTruthy();
});

it("asks about one panel, or says it was not understood, inside the same branch", async () => {
  const { onAsk } = card();
  const first = (await screen.findAllByRole("region", { name: /^A / }))[0];
  fireEvent.click(within(first).getByRole("button", { name: /没看懂/ }));
  expect(onAsk).toHaveBeenCalledWith(expect.stringMatching(/^A「.+」这一块我没看懂/), "x1");
  fireEvent.click(within(first).getByRole("button", { name: /^追问 A/ }));
  const box = screen.getByLabelText("接着问这一页") as HTMLTextAreaElement;
  await waitFor(() => expect(box.value).toMatch(/^关于 A「.+」：$/));
});

it("folds into one line with the conclusion", async () => {
  card({ expanded: false });
  const toggle = await screen.findByRole("button", { name: new RegExp(doc.title) });
  expect(toggle.getAttribute("aria-expanded")).toBe("false");
  expect(screen.queryByLabelText("接着问这一页")).toBeNull();
});

it("exports a static single-file page without scripts or controls", async () => {
  card();
  await screen.findAllByRole("region", { name: /^A / });
  const root = document.querySelector(".xp-doc") as HTMLElement;
  const evil = document.createElement("script");
  evil.textContent = "alert(1)";
  root.append(evil);
  const html = explainerHtml(root, { title: "T <b>", source: "Paper" });
  expect(html).not.toMatch(/<script/i);
  expect(html).not.toMatch(/<button/i);
  expect(html).toContain("T &lt;b&gt;");
  expect(html).toContain("xp-grid");
});

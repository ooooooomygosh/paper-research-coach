import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import Dialog from "../src/Dialog";

beforeEach(() => {
  Object.defineProperties(HTMLDialogElement.prototype, {
    showModal: { configurable: true, value: function (this: HTMLDialogElement) { this.open = true; } },
    close: { configurable: true, value: function (this: HTMLDialogElement) { this.open = false; } },
  });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("wraps at a summary and excludes collapsed details even when their descendants have rects", () => {
  render(<Dialog label="Import" onClose={vi.fn()}>
    <button>First</button>
    <details><summary>More</summary><input aria-label="Hidden path" /></details>
    <button disabled>Save</button>
  </Dialog>);
  const first = screen.getByRole("button", { name: "First" });
  const summary = screen.getByText("More");
  // Reproduce Chromium retaining boxes for controls inside collapsed details.
  for (const element of [first, summary, screen.getByLabelText("Hidden path")])
    vi.spyOn(element, "getClientRects").mockReturnValue([{}] as unknown as DOMRectList);
  summary.focus();
  fireEvent.keyDown(summary, { key: "Tab" });
  expect(document.activeElement).toBe(first);
  fireEvent.keyDown(first, { key: "Tab", shiftKey: true });
  expect(document.activeElement).toBe(summary);
});

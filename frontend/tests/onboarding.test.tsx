import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import PageNavigation from "../src/PageNavigation";
import Dialog from "../src/Dialog";
import { ImportModal } from "../src/PaperDialogs";
import { filterPapers } from "../src/library-search";

beforeEach(() => {
  // jsdom has no browser top layer; focus containment is checked in Chromium.
  Object.defineProperties(HTMLDialogElement.prototype, {
    showModal: { configurable: true, value: function (this: HTMLDialogElement) { this.open = true; } },
    close: { configurable: true, value: function (this: HTMLDialogElement) { this.open = false; } },
  });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it("does not move or persist the PDF cursor while typing a multi-digit page", () => {
  const move = vi.fn();
  render(<PageNavigation page={1} count={30} onChange={move} />);
  const input = screen.getByLabelText("阅读页码") as HTMLInputElement;
  fireEvent.change(input, { target: { value: "1" } });
  fireEvent.change(input, { target: { value: "12" } });
  expect(move).not.toHaveBeenCalled();
  fireEvent.keyDown(input, { key: "Enter" });
  expect(move).toHaveBeenCalledExactlyOnceWith(11);
});

it("commits on blur, clamps bounds and rejects non-integer page drafts", () => {
  const move = vi.fn();
  render(<PageNavigation page={2} count={20} onChange={move} />);
  const input = screen.getByLabelText("阅读页码") as HTMLInputElement;
  for (const invalid of ["", "oops", "1.5", "-1"]) {
    fireEvent.change(input, { target: { value: invalid } });
    fireEvent.blur(input);
    expect(input.value).toBe("3");
  }
  expect(move).not.toHaveBeenCalled();
  fireEvent.change(input, { target: { value: "999" } });
  fireEvent.blur(input);
  expect(move).toHaveBeenLastCalledWith(19);
  expect(input.value).toBe("20");
});

it("cancels page editing with Escape without dismissing the reading surface", () => {
  const escape = vi.fn(), move = vi.fn();
  const view = render(<div onKeyDown={escape}><PageNavigation page={2} count={20} onChange={move} /></div>);
  const input = screen.getByLabelText("阅读页码") as HTMLInputElement;
  fireEvent.change(input, { target: { value: "19" } });
  fireEvent.keyDown(input, { key: "Escape" });
  expect(input.value).toBe("3");
  expect(escape).not.toHaveBeenCalled();
  expect(move).not.toHaveBeenCalled();
  view.rerender(<PageNavigation page={8} count={20} onChange={move} />);
  expect((screen.getByLabelText("阅读页码") as HTMLInputElement).value).toBe("9");
});

it("disables navigation when there is no PDF", () => {
  render(<PageNavigation page={0} count={0} onChange={vi.fn()} />);
  expect((screen.getByLabelText("阅读页码") as HTMLInputElement).disabled).toBe(true);
  expect((screen.getByLabelText("下一页") as HTMLButtonElement).disabled).toBe(true);
});

it("matches title, author, year and DOI together and normalizes full-width input", () => {
  const papers = [{ id: "p", title: "Beam Timing", authors: "A. Reader", year: "2025", doi: "10.123/p" }, { id: "q", title: "Other" }];
  expect(filterPapers(papers, "reader ２０２５ beam")).toEqual([papers[0]]);
  expect(filterPapers(papers, "10.123/P")).toEqual([papers[0]]);
  expect(filterPapers(papers, "reader 2024")).toEqual([]);
  expect(filterPapers(papers, "   ")).toBe(papers);
});

it("opens a labelled native modal and restores the invoking control on unmount", () => {
  const opener = document.createElement("button");
  document.body.append(opener); opener.focus();
  const close = vi.fn();
  const view = render(<Dialog label="Example" onClose={close}><input aria-label="Title" /></Dialog>);
  const dialog = screen.getByRole("dialog", { name: "Example" }) as HTMLDialogElement;
  expect(dialog.open).toBe(true);
  fireEvent.keyDown(dialog, { key: "Escape" });
  expect(close).toHaveBeenCalledOnce();
  view.unmount();
  expect(document.activeElement).toBe(opener); opener.remove();
});

it("does not dismiss a busy modal", () => {
  const close = vi.fn();
  render(<Dialog label="Busy" onClose={close} canClose={false}>Saving</Dialog>);
  fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
  fireEvent(screen.getByRole("dialog"), new Event("cancel", { bubbles: true, cancelable: true }));
  expect(close).not.toHaveBeenCalled();
});

it("supports a single PDF drop, preserves an edited title and rejects other formats", () => {
  render(<ImportModal onClose={vi.fn()} onDone={vi.fn()} report={vi.fn()} />);
  const target = document.querySelector(".file-drop")!;
  fireEvent.drop(target, { dataTransfer: { files: [new File(["pdf"], "first.pdf", { type: "application/pdf" })] } });
  const title = screen.getByLabelText("论文名称") as HTMLInputElement;
  expect(title.value).toBe("first");
  fireEvent.change(title, { target: { value: "My reading title" } });
  fireEvent.drop(target, { dataTransfer: { files: [new File(["pdf"], "second.pdf")] } });
  expect(title.value).toBe("My reading title");
  fireEvent.drop(target, { dataTransfer: { files: [new File(["text"], "bad.txt")] } });
  expect(screen.getByRole("alert").textContent).toContain("请选择 PDF");
  expect(title.value).toBe("My reading title");
});

it("retains the selected file and goal after an import failure", async () => {
  const request = vi.fn().mockResolvedValue({ ok: false, json: async () => ({ error: "PDF could not be read" }) });
  vi.stubGlobal("fetch", request);
  const done = vi.fn();
  render(<ImportModal onClose={vi.fn()} onDone={done} report={vi.fn()} />);
  fireEvent.drop(document.querySelector(".file-drop")!, { dataTransfer: { files: [new File(["pdf"], "retry.pdf")] } });
  fireEvent.change(screen.getByLabelText("这次阅读为了什么？（可选）"), { target: { value: "Check the control" } });
  fireEvent.click(screen.getByRole("button", { name: "打开论文" }));
  expect((await screen.findByRole("alert")).textContent).toContain("PDF could not be read");
  expect(screen.getByText("retry.pdf")).toBeTruthy();
  expect((screen.getByLabelText("这次阅读为了什么？（可选）") as HTMLTextAreaElement).value).toBe("Check the control");
  await waitFor(() => expect((screen.getByRole("button", { name: "打开论文" }) as HTMLButtonElement).disabled).toBe(false));
  expect(done).not.toHaveBeenCalled();
});

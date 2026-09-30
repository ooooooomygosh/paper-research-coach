import { useState } from "react";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import PdfReader from "../src/PdfReader";
const mock = vi.hoisted(() => ({
  count: 3,
  fail: -1,
  calls: [] as number[][],
}));
vi.mock("pdfjs-dist", () => ({
  GlobalWorkerOptions: {},
  TextLayer: class {
    render() {
      return Promise.resolve();
    }
    cancel() {}
  },
  getDocument: () => {
    const count = mock.count;
    return {
      destroy: vi.fn(),
      promise: Promise.resolve({
        numPages: count,
        getPageLabels: async () => null,
        getPage: async (page: number) => {
          mock.calls.push([count, page]);
          if (page > count || page === mock.fail)
            throw new Error("Page unavailable");
          return {
            getViewport: ({ scale }: { scale: number }) => ({
              scale,
              width: 600 * scale,
              height: 800 * scale,
              convertToViewportPoint: (x: number, y: number) => [
                x * scale,
                (800 - y) * scale,
              ],
              convertToPdfPoint: (x: number, y: number) => [
                x / scale,
                800 - y / scale,
              ],
            }),
            render: () => ({ promise: Promise.resolve(), cancel: vi.fn() }),
            getTextContent: async () => ({ items: [1] }),
          };
        },
      }),
    };
  },
}));
function Reader({ version }: { version: string }) {
  const [page, setPage] = useState(2);
  return (
    <PdfReader
      paper={{
        id: "p",
        revision: 1,
        source_version: version,
        page_count: mock.count,
      }}
      page={page}
      setPage={setPage}
      onAnchor={vi.fn()}
      focusAnchor={null}
    />
  );
}
beforeEach(() => {
  mock.count = 3;
  mock.fail = -1;
  mock.calls = [];
  HTMLElement.prototype.scrollIntoView = vi.fn();
});
afterEach(cleanup);
it("bounds the page when replacing a PDF with a shorter version", async () => {
  const view = render(<Reader version="old" />);
  await waitFor(() => expect(mock.calls).toContainEqual([3, 3]));
  mock.count = 1;
  view.rerender(<Reader version="new" />);
  await waitFor(() => expect(mock.calls).toContainEqual([1, 1]));
  expect(mock.calls).not.toContainEqual([1, 3]);
  expect(document.querySelector("canvas")).toBeTruthy();
});
it("can render another page after a page-rendering failure", async () => {
  mock.fail = 3;
  render(<Reader version="old" />);
  expect(await screen.findByRole("alert")).toBeTruthy();
  fireEvent.click(screen.getByLabelText("上一页"));
  await waitFor(() => expect(mock.calls).toContainEqual([3, 2]));
  await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
  expect(document.querySelector("canvas")).toBeTruthy();
});
it("locates a region using the current PDF.js point API and follows zoom", async () => {
  const props = {
    paper: { id: "p", revision: 1, source_version: "current", page_count: 3 },
    page: 0,
    setPage: vi.fn(),
    onAnchor: vi.fn(),
    focusAnchor: null as any,
  };
  const view = render(<PdfReader {...props} />);
  await waitFor(() => expect(mock.calls).toContainEqual([3, 1]));
  const anchor = {
    paper_id: "p",
    source_version: "current",
    page_index: 0,
    status: "verified",
    rects: [[100, 200, 160, 260]],
  };
  view.rerender(<PdfReader {...props} focusAnchor={anchor} />);
  await waitFor(() => {
    const highlight = document.querySelector<HTMLElement>(".anchor-highlight");
    expect(highlight).not.toBeNull();
    expect(parseFloat(highlight!.style.left)).toBeCloseTo(110);
    expect(parseFloat(highlight!.style.top)).toBeCloseTo(594);
    expect(parseFloat(highlight!.style.width)).toBeCloseTo(66);
    expect(parseFloat(highlight!.style.height)).toBeCloseTo(66);
    expect(HTMLElement.prototype.scrollIntoView).toHaveBeenCalled();
  });
  fireEvent.click(screen.getByLabelText("放大"));
  await waitFor(() => {
    const highlight = document.querySelector<HTMLElement>(".anchor-highlight");
    expect(highlight).not.toBeNull();
    expect(parseFloat(highlight!.style.left)).toBeCloseTo(125);
    expect(parseFloat(highlight!.style.top)).toBeCloseTo(675);
    expect(parseFloat(highlight!.style.width)).toBeCloseTo(75);
  });
  view.rerender(
    <PdfReader {...props} focusAnchor={{ ...anchor, source_version: "old" }} />,
  );
  expect(document.querySelector(".anchor-highlight")).toBeNull();
});

it("shows only current verified page annotations and locating one does not rebind a draft", async () => {
  const anchor = {
    paper_id: "p",
    source_version: "v",
    page_index: 0,
    status: "verified",
    rects: [[10, 20, 30, 40]],
  };
  const note = {
    id: "n",
    paper_id: "p",
    revision: 1,
    content: "Zotero source thought",
    author: "external",
    read_only: true,
    anchor,
  };
  const locate = vi.fn(),
    select = vi.fn();
  const props = {
    paper: { id: "p", source_version: "v", revision: 1, page_count: 3 },
    page: 0,
    setPage: vi.fn(),
    focusAnchor: null,
    onAnchor: select,
    onLocateNote: locate,
  };
  render(
    <PdfReader
      {...props}
      notes={[
        note,
        { ...note, id: "old", anchor: { ...anchor, source_version: "old" } },
        { ...note, id: "inferred", anchor: { ...anchor, status: "inferred" } },
        { ...note, id: "elsewhere", anchor: { ...anchor, page_index: 2 } },
        {
          ...note,
          id: "other",
          paper_id: "other",
          anchor: { ...anchor, paper_id: "other" },
        },
      ]}
    />,
  );
  await waitFor(() =>
    expect(document.querySelectorAll(".saved-annotation")).toHaveLength(1),
  );
  fireEvent.click(screen.getByText("本页批注 · 1"));
  fireEvent.click(screen.getByRole("button", { name: /Zotero 笔记 · 只读/ }));
  expect(locate).toHaveBeenCalledWith(anchor);
  expect(select).not.toHaveBeenCalled();
});

it("fits the page width and keeps keyboard navigation out of page input editing", async () => {
  const setPage = vi.fn();
  render(
    <PdfReader
      paper={{ id: "p", source_version: "v", revision: 1, page_count: 3 }}
      page={0}
      setPage={setPage}
      focusAnchor={null}
      onAnchor={vi.fn()}
    />,
  );
  await waitFor(() =>
    expect(
      document.querySelector('.pdf-page[data-page-index="0"]'),
    ).not.toBeNull(),
  );
  const box = document.querySelector<HTMLElement>(".pdf-scroll")!;
  Object.defineProperty(box, "clientWidth", { value: 500 });
  box.style.paddingLeft = "10px";
  box.style.paddingRight = "10px";
  fireEvent.click(screen.getByLabelText("适应宽度"));
  await waitFor(() => expect(screen.getByText("80%")).toBeTruthy());
  fireEvent.click(screen.getByLabelText("适应宽度"));
  await waitFor(() => expect(screen.getByText("80%")).toBeTruthy());
  fireEvent.keyDown(screen.getByLabelText("PDF 页码"), { key: "ArrowRight" });
  expect(setPage).not.toHaveBeenCalled();
  fireEvent.keyDown(screen.getByLabelText("PDF 阅读器"), { key: "ArrowRight" });
  expect(setPage).toHaveBeenCalledWith(1);
});

it("ignores focused geometry from another paper even when the PDF version matches", async () => {
  render(
    <PdfReader
      paper={{ id: "p", source_version: "v", revision: 1, page_count: 3 }}
      page={0}
      setPage={vi.fn()}
      onAnchor={vi.fn()}
      focusAnchor={{
        paper_id: "other",
        source_version: "v",
        page_index: 0,
        status: "verified",
        rects: [[1, 2, 3, 4]],
      }}
    />,
  );
  await waitFor(() =>
    expect(
      document.querySelector('.pdf-page[data-page-index="0"]'),
    ).not.toBeNull(),
  );
  expect(document.querySelector(".anchor-highlight")).toBeNull();
});

it("restores the saved page's scroll after the parent loads its page asynchronously", async () => {
  const key = "prc-viewport-delayed:v";
  localStorage.setItem(
    key,
    JSON.stringify({ page: 2, top: 0.5, left: 0, zoom: 1, fit: true }),
  );
  const props = {
    paper: { id: "delayed", source_version: "v", revision: 1, page_count: 3 },
    setPage: vi.fn(),
    onAnchor: vi.fn(),
    focusAnchor: null,
  };
  const view = render(<PdfReader {...props} page={0} />);
  const box = document.querySelector<HTMLElement>(".pdf-scroll")!;
  Object.defineProperty(box, "scrollHeight", { value: 1000 });
  Object.defineProperty(box, "clientHeight", { value: 400 });
  await waitFor(() => expect(box.scrollTop).toBe(300));
  view.rerender(<PdfReader {...props} page={2} />);
  await waitFor(() =>
    expect(
      document.querySelector('.pdf-page[data-page-index="2"]'),
    ).toBeTruthy(),
  );
  await waitFor(() => expect(box.scrollTop).toBe(300));
  localStorage.removeItem(key);
});

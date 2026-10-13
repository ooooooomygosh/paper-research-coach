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
  annotations: {} as Record<number, any[]>,
}));
vi.mock("pdfjs-dist/legacy/build/pdf.mjs", () => ({
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
        getDestination: async (name: string) => (name === "fig3" ? [{ num: 30 }, { name: "XYZ" }, 0, 700, null] : null),
        getPageIndex: async (ref: { num: number }) => ref.num / 10 - 1,
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
            getAnnotations: async () => mock.annotations[page] || [],
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
  mock.annotations = {};
  HTMLElement.prototype.scrollIntoView = vi.fn();
  window.requestAnimationFrame = ((cb: FrameRequestCallback) => setTimeout(() => cb(0), 0)) as any;
  window.cancelAnimationFrame = ((id: number) => clearTimeout(id)) as any;
});
/** jsdom has no layout: give the scroller a visible height. */
function sized(height = 400) {
  const box = document.querySelector<HTMLElement>(".pdf-scroll")!;
  Object.defineProperty(box, "clientHeight", { configurable: true, value: height });
  return box;
}
afterEach(cleanup);
it("bounds the page when replacing a PDF with a shorter version", async () => {
  const view = render(<Reader version="old" />);
  await waitFor(() => expect(mock.calls).toContainEqual([3, 3]));
  mock.count = 1;
  view.rerender(<Reader version="new" />);
  await waitFor(() => expect(mock.calls).toContainEqual([1, 1]));
  expect(mock.calls).not.toContainEqual([1, 3]);
  await waitFor(() => expect(document.querySelector('.pdf-page[data-page-index="0"] canvas')).toBeTruthy());
  expect(document.querySelectorAll(".pdf-page")).toHaveLength(1);
});
it("keeps the other pages readable when one page fails to draw", async () => {
  mock.fail = 3;
  render(<Reader version="old" />);
  const alert = await screen.findByRole("alert");
  expect(alert.closest(".pdf-page")?.getAttribute("data-slot")).toBe("2");
  await waitFor(() => expect(document.querySelector('.pdf-page[data-page-index="1"]')).toBeTruthy());
  expect(document.querySelectorAll("canvas").length).toBeGreaterThan(0);
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
  fireEvent.click(screen.getByLabelText("PDF 放大"));
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
  fireEvent.click(screen.getByLabelText("PDF 适应宽度"));
  await waitFor(() => expect(screen.getByLabelText("PDF 缩放比例").textContent).toBe("80%"));
  fireEvent.click(screen.getByLabelText("PDF 适应宽度"));
  await waitFor(() => expect(screen.getByLabelText("PDF 缩放比例").textContent).toBe("80%"));
  fireEvent.keyDown(screen.getByLabelText("阅读页码"), { key: "ArrowRight" });
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

it("restores the saved spot inside a page after the parent loads its page asynchronously", async () => {
  const key = "prc-viewport-delayed:v";
  localStorage.setItem(key, JSON.stringify({ page: 2, frac: 0.5, left: 0, zoom: 1, fit: false }));
  const props = {
    paper: { id: "delayed", source_version: "v", revision: 1, page_count: 3 },
    setPage: vi.fn(),
    onAnchor: vi.fn(),
    focusAnchor: null,
  };
  const view = render(<PdfReader {...props} page={0} />);
  await waitFor(() => expect(document.querySelector(".pdf-stack")).toBeTruthy());
  const box = document.querySelector<HTMLElement>(".pdf-scroll")!;
  expect(box.scrollTop).toBe(0);
  view.rerender(<PdfReader {...props} page={2} />);
  // Page tops at zoom 1: 0, 814, 1628 (800px pages, 14px gaps); half of page 3 is above the edge.
  await waitFor(() => expect(box.scrollTop).toBe(2028));
  localStorage.removeItem(key);
});

it("reports the page under the reading line while scrolling, and scrolls to jumps", async () => {
  const key = "prc-viewport-scroll:v";
  localStorage.setItem(key, JSON.stringify({ zoom: 1, fit: false }));
  const setPage = vi.fn();
  const props = { paper: { id: "scroll", source_version: "v", revision: 1, page_count: 3 }, setPage, onAnchor: vi.fn(), focusAnchor: null };
  const view = render(<PdfReader {...props} page={0} />);
  await waitFor(() => expect(document.querySelector('.pdf-page[data-page-index="0"]')).toBeTruthy());
  const box = sized(400);
  box.scrollTop = 1500; // the reading line at 1700 is on the third page
  fireEvent.scroll(box);
  await waitFor(() => expect(setPage).toHaveBeenCalledWith(2, "scroll"));
  setPage.mockClear();
  view.rerender(<PdfReader {...props} page={1} />);
  await waitFor(() => expect(box.scrollTop).toBe(814));
  // Our own scroll is not mistaken for the reader's.
  fireEvent.scroll(box);
  await new Promise((r) => setTimeout(r, 5));
  expect(setPage).not.toHaveBeenCalled();
  fireEvent.keyDown(screen.getByLabelText("PDF 阅读器"), { key: "ArrowRight" });
  expect(setPage).toHaveBeenCalledWith(2);
  localStorage.removeItem(key);
});

it("draws only the pages near the reading position", async () => {
  mock.count = 40;
  render(<PdfReader paper={{ id: "long", source_version: "v", revision: 1, page_count: 40 }} page={0} setPage={vi.fn()} onAnchor={vi.fn()} focusAnchor={null} />);
  await waitFor(() => expect(document.querySelectorAll(".pdf-page")).toHaveLength(40));
  await waitFor(() => expect(document.querySelector('.pdf-page[data-page-index="1"]')).toBeTruthy());
  const drawn = new Set(mock.calls.map(([, p]) => p));
  expect(drawn.has(30)).toBe(false);
  expect(document.querySelectorAll("canvas").length).toBeLessThan(8);
});

it("follows links inside the PDF to the target page and keeps only safe external links", async () => {
  mock.annotations[1] = [
    { subtype: "Link", rect: [10, 10, 40, 30], dest: "fig3" },
    { subtype: "Link", rect: [50, 10, 90, 30], url: "https://example.org/paper" },
    { subtype: "Link", rect: [50, 40, 90, 60], url: "javascript:alert(1)" },
  ];
  const setPage = vi.fn();
  render(<PdfReader paper={{ id: "links", source_version: "v", revision: 1, page_count: 3 }} page={0} setPage={setPage} onAnchor={vi.fn()} focusAnchor={null} />);
  fireEvent.click(await screen.findByRole("button", { name: "跳到第 3 页" }));
  expect(setPage).toHaveBeenCalledWith(2);
  const external = screen.getByRole("link", { name: /example.org/ });
  expect(external.getAttribute("rel")).toBe("noopener noreferrer");
  expect(document.querySelectorAll(".pdf-link")).toHaveLength(2);
});

it("restores only the matching translated rendition, never another layout or regenerated file", async () => {
  const rendition = { job_id: "job", view: "dual" as const, document_version: "a".repeat(64) };
  const anchor = { paper_id: "p", source_version: "v", status: "unresolved", page_index: null,
    rects: [], rendition: { ...rendition, page_index: 0, quote: "", rects: [[100, 200, 160, 260]] } };
  const note = { id: "translated", paper_id: "p", revision: 1, content: "My translated-page note", anchor, annotation_type: "rectangle" };
  const props = { paper: { id: "p", source_version: "v", revision: 1, page_count: 3 }, page: 0, setPage: vi.fn(), onAnchor: vi.fn(), focusAnchor: null, notes: [note] };
  const view = render(<PdfReader {...props} derived documentKey="job:dual" rendition={rendition} />);
  await waitFor(() => expect(document.querySelectorAll(".saved-annotation.rectangle")).toHaveLength(1));
  const box = document.querySelector<HTMLElement>(".saved-annotation")!;
  expect(parseFloat(box.style.left)).toBeCloseTo(110);
  fireEvent.click(screen.getByLabelText("PDF 放大"));
  await waitFor(() => expect(parseFloat(document.querySelector<HTMLElement>(".saved-annotation")!.style.left)).toBeCloseTo(125));
  view.rerender(<PdfReader {...props} derived documentKey="job:mono" rendition={{ ...rendition, view: "mono" }} />);
  await waitFor(() => expect(document.querySelector('.pdf-page[data-page-index="0"]')).toBeTruthy());
  expect(document.querySelector(".saved-annotation")).toBeNull();
  view.rerender(<PdfReader {...props} derived documentKey="job:new" rendition={{ ...rendition, document_version: "b".repeat(64) }} />);
  expect(document.querySelector(".saved-annotation")).toBeNull();
  view.rerender(<PdfReader {...props} />);
  expect(document.querySelector(".saved-annotation")).toBeNull();
});

it("zooms with trackpad pinch events but leaves ordinary wheel scrolling native", async () => {
  render(<PdfReader paper={{ id: "wheel", source_version: "v", revision: 1, page_count: 3 }} page={0} setPage={vi.fn()} onAnchor={vi.fn()} focusAnchor={null} />);
  await waitFor(() => expect(document.querySelector('.pdf-page[data-page-index="0"]')).toBeTruthy());
  const scroll = document.querySelector(".pdf-scroll")!;
  const wheel = new WheelEvent("wheel", { deltaY: -40, bubbles: true, cancelable: true });
  fireEvent(scroll, wheel);
  expect(wheel.defaultPrevented).toBe(false);
  expect(screen.getByLabelText("PDF 缩放比例").textContent).toBe("110%");
  const calls = mock.calls.length;
  fireEvent.wheel(scroll, { ctrlKey: true, deltaY: -40, clientX: 200, clientY: 200 });
  expect(parseInt(screen.getByLabelText("PDF 缩放比例").textContent!)).toBeGreaterThan(110);
  expect(mock.calls).toHaveLength(calls); // Gesture preview reuses the existing canvas.
  await waitFor(() => expect(mock.calls.length).toBeGreaterThan(calls));
  expect(document.querySelector<HTMLElement>(".pdf-stack")!.style.transform).toBe("");
});

it("draws numbered coach marks and offers one click back to the earlier page", async () => {
  const setPage = vi.fn(), dismiss = vi.fn(), stop = vi.fn();
  render(<PdfReader paper={{ id: "marks", source_version: "v", revision: 1, page_count: 3 }} page={1} setPage={setPage} onAnchor={vi.fn()} focusAnchor={null}
    coachMarks={{ page_index: 1, marks: [{ n: 1, rects: [[100, 200, 160, 260]] }, { n: 2, rects: [[100, 300, 160, 320]] }] }}
    returnTo={{ page: 0, to: 1, key: "f1" }} onDismissReturn={dismiss} onFollowCoach={stop} />);
  await waitFor(() => expect(document.querySelectorAll('.pdf-page[data-slot="1"] .coach-mark')).toHaveLength(2));
  expect(document.querySelector(".coach-mark-n")!.textContent).toBe("1");
  expect(HTMLElement.prototype.scrollIntoView).toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "回到第 1 页" }));
  expect(setPage).toHaveBeenCalledWith(0);
  expect(dismiss).toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "不要自动翻页" }));
  expect(stop).toHaveBeenCalledWith(false);
});

it("never draws coach marks on a translated layout", async () => {
  const rendition = { job_id: "job", view: "mono" as const, document_version: "a".repeat(64) };
  render(<PdfReader paper={{ id: "p", source_version: "v", revision: 1, page_count: 3 }} page={0} setPage={vi.fn()} onAnchor={vi.fn()} focusAnchor={null}
    derived documentKey="job:mono" rendition={rendition} coachMarks={{ page_index: 0, marks: [{ n: 1, rects: [[1, 2, 30, 40]] }] }} />);
  await waitFor(() => expect(document.querySelector('.pdf-page[data-page-index="0"]')).toBeTruthy());
  expect(document.querySelector(".coach-mark")).toBeNull();
});

it("keeps the reader on the same page after switching to another rendition", async () => {
  localStorage.setItem("prc-viewport-switch:v", JSON.stringify({ zoom: 1, fit: false }));
  localStorage.setItem("prc-viewport-switch:v:job:mono", JSON.stringify({ zoom: 1, fit: false }));
  const props = { paper: { id: "switch", source_version: "v", revision: 1, page_count: 3 }, page: 1, setPage: vi.fn(), onAnchor: vi.fn(), focusAnchor: null };
  const view = render(<PdfReader {...props} />);
  const box = document.querySelector<HTMLElement>(".pdf-scroll")!;
  await waitFor(() => expect(box.scrollTop).toBe(814));
  view.rerender(<PdfReader {...props} derived documentKey="job:mono" fileUrl="/mono.pdf"
    rendition={{ job_id: "job", view: "mono", document_version: "a".repeat(64) }} />);
  box.scrollTop = 0; // a browser resets the scroll while the old document is removed
  await waitFor(() => expect(document.querySelector('.pdf-page[data-derived="job:mono"]')).toBeTruthy());
  await waitFor(() => expect(box.scrollTop).toBe(814));
});

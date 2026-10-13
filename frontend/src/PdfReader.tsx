import PageNavigation from "./PageNavigation";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  getDocument,
  GlobalWorkerOptions,
  type PDFDocumentProxy,
} from "pdfjs-dist/legacy/build/pdf.mjs";
// The legacy build polyfills very recent APIs (e.g. Map#getOrInsertComputed,
// Math.sumPrecise) that the modern pdf.js 6 build calls unconditionally; without
// it, pages fail to render in browsers that are only a few months old.
import worker from "pdfjs-dist/legacy/build/pdf.worker.min.mjs?url";
import "./pdf-text-layer.css";
import "./reading-experience.css";
import "./pdf-controls.css";
import { boundZoom, MIN_ZOOM, MAX_ZOOM, usePdfZoom, type ZoomFocus } from "./usePdfZoom";
import { Scan, ZoomIn, ZoomOut, Download, Maximize } from "lucide-react";
import { anchorFor, visibleAnchor, type Row } from "./api";
import PdfNavigation from "./PdfNavigation";
import PdfPage, { type Mark, type Viewport } from "./PdfPage";
GlobalWorkerOptions.workerSrc = worker;

/** Space between pages in the scrolling stack, in CSS pixels (not scaled by zoom). */
export const PAGE_GAP = 14;
/** The reading line: the page under this fraction of the visible height is "the current page". */
const READING_LINE = 0.5;
const NONE: never[] = [];

export type CoachMarks = { page_index: number; marks: Mark[] } | null;

export default function PdfReader({
  paper,
  page,
  setPage,
  onAnchor,
  focusAnchor,
  notes = [],
  onLocateNote,
  toolsContainer,
  fitRequest = 0,
  fileUrl,
  documentKey = "original",
  derived = false,
  rendition,
  draftAnchor,
  onExport,
  exporting = false,
  view = "original",
  availableViews,
  onViewChange,
  coachMarks = null,
}: {
  paper: Row;
  page: number;
  /** `how === "scroll"` when the reader scrolled onto another page; otherwise it is a jump. */
  setPage: (n: number, how?: "scroll") => void;
  onAnchor: (a: any, placement?: { x: number; y: number }) => void;
  focusAnchor: any;
  notes?: Row[];
  onLocateNote?: (a: any) => void;
  toolsContainer?: HTMLElement | null;
  fitRequest?: number;
  fileUrl?: string;
  documentKey?: string;
  derived?: boolean;
  rendition?: { job_id: string; view: "mono" | "dual"; document_version: string } | null;
  draftAnchor?: any;
  onExport?: () => void;
  exporting?: boolean;
  view?: "original" | "mono" | "dual";
  availableViews?: { mono: boolean; dual: boolean };
  onViewChange?: (view: "original" | "mono" | "dual") => void;
  /** Sentences the coach pointed at; drawn only on the original PDF. */
  coachMarks?: CoachMarks;
}) {
  const scroller = useRef<HTMLDivElement>(null),
    stack = useRef<HTMLDivElement>(null),
    viewports = useRef<(Viewport | null)[]>([]);
  const [doc, setDoc] = useState<PDFDocumentProxy | null>(null),
    [error, setError] = useState(""),
    [zoom, setZoom] = useState(1.1),
    [sizes, setSizes] = useState<{ width: number; height: number }[]>([]),
    [region, setRegion] = useState(false),
    [scanPages, setScanPages] = useState<Set<number>>(() => new Set()),
    [range, setRange] = useState<[number, number]>([0, 0]),
    [readyPages, setReadyPages] = useState<Set<number>>(() => new Set()),
    [searchTerm, setSearchTerm] = useState("");
  const labels = useRef<string[] | null>(null);
  const [fitWidth, setFitWidth] = useState(true);
  const docKey = paper.id + ":" + paper.source_version + ":" + documentKey;
  const positionKey = "prc-viewport-" + paper.id + ":" + paper.source_version + (documentKey === "original" ? "" : ":" + documentKey);
  const count = doc?.numPages || 0;

  // Page geometry. Offsets are relative to the top of the stack and follow the zoom.
  const layout = useMemo(() => {
    const tops: number[] = [];
    let y = 0, width = 0;
    for (const s of sizes) {
      tops.push(y);
      y += s.height * zoom + PAGE_GAP;
      width = Math.max(width, s.width * zoom);
    }
    return { tops, height: Math.max(0, y - PAGE_GAP), width };
  }, [sizes, zoom]);
  const latest = useRef({ layout, zoom, page, sizes, count });
  latest.current = { layout, zoom, page, sizes, count };

  /** Which page holds a stack-relative y. */
  function pageAt(y: number, tops = latest.current.layout.tops) {
    let lo = 0, hi = tops.length - 1;
    while (lo < hi) {
      const mid = (lo + hi + 1) >> 1;
      if (tops[mid] <= y) lo = mid; else hi = mid - 1;
    }
    return Math.max(0, lo);
  }
  /** Where the stack starts inside the scrolled content (the scroller is its offset parent). */
  function stackOrigin() {
    const box = scroller.current!, s = stack.current!;
    return { left: s.offsetLeft, top: s.offsetTop, box: box.getBoundingClientRect() };
  }

  // --- Position memory -------------------------------------------------------------------
  // Saved as "page + fraction of that page above the top edge", so it survives zoom changes.
  const pending = useRef<{ page: number; frac: number; left: number } | null>(null);
  /** The scrollTop we last set ourselves; scroll events at that position are not the reader's. */
  const programmatic = useRef<number | null>(null);
  /** The page we last reported from scrolling. */
  const reported = useRef(page);
  const [fromScroll, setFromScroll] = useState(false);

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(positionKey) || "{}");
      setFitWidth(saved.fit !== false);
      if (Number.isFinite(saved.zoom)) setZoom(boundZoom(saved.zoom));
      pending.current = Number.isInteger(saved.page)
        ? { page: saved.page, frac: Number(saved.frac) || 0, left: Number(saved.left) || 0 }
        : null;
    } catch {
      pending.current = null;
    }
  }, [positionKey]);

  function save() {
    const box = scroller.current, { layout: l, page: p, sizes: s } = latest.current;
    if (!box || !stack.current || !s.length) return;
    const origin = stackOrigin();
    const h = Math.max(1, (l.tops[p + 1] ?? l.height + PAGE_GAP) - l.tops[p] - PAGE_GAP);
    const frac = (box.scrollTop - origin.top - l.tops[p]) / h;
    try {
      localStorage.setItem(positionKey, JSON.stringify({
        page: p, frac: Number.isFinite(frac) ? Math.round(frac * 1000) / 1000 : 0,
        left: box.scrollLeft / Math.max(1, box.scrollWidth - box.clientWidth), zoom: latest.current.zoom, fit: fitWidth,
      }));
    } catch { /* storage unavailable: position memory is a convenience */ }
  }

  function scrollToPage(target: number, opts: { frac?: number; left?: number; pdfTop?: number | null } = {}) {
    const box = scroller.current, { layout: l, sizes: s, zoom: z } = latest.current;
    if (!box || !stack.current || !l.tops.length) return;
    const t = Math.max(0, Math.min(target, l.tops.length - 1));
    const origin = stackOrigin();
    let within = 0;
    if (opts.pdfTop != null && Number.isFinite(opts.pdfTop)) {
      const v = viewports.current[t];
      within = v ? v.convertToViewportPoint(0, opts.pdfTop)[1] : (s[t].height - opts.pdfTop) * z;
      within = Math.max(0, within - 24);
    } else if (opts.frac) within = opts.frac * s[t].height * z;
    box.scrollTop = Math.max(0, origin.top + l.tops[t] + within);
    if (opts.left != null) box.scrollLeft = opts.left * Math.max(0, box.scrollWidth - box.clientWidth);
    programmatic.current = box.scrollTop;
    updateRange();
  }

  // --- Loading -----------------------------------------------------------------------------
  useEffect(() => {
    let disposed = false;
    setDoc(null);
    setError("");
    setSizes([]);
    setScanPages(new Set());
    setReadyPages(new Set());
    setRegion(false);
    setSearchTerm("");
    viewports.current = [];
    labels.current = null;
    const load = getDocument({
      url: fileUrl || "/api/pdf/" + paper.id,
      withCredentials: true,
      cMapUrl: "/pdf-assets/cmaps/",
      cMapPacked: true,
      standardFontDataUrl: "/pdf-assets/standard_fonts/",
      wasmUrl: "/pdf-assets/wasm/",
    });
    load.promise
      .then(async (d) => {
        const pageLabels = await d.getPageLabels();
        // Every page starts with the first page's size; each page corrects it when drawn.
        const first = (await d.getPage(1)).getViewport({ scale: 1 });
        if (disposed) return;
        labels.current = pageLabels;
        setSizes(Array.from({ length: d.numPages }, () => ({ width: first.width, height: first.height })));
        setDoc(d);
      })
      .catch((e) => {
        if (disposed) return;
        console.warn("PDF document load failed", e);
        setError("PDF 暂不可用。请检查文件位置；换版后需要重新确认锚点。");
      });
    return () => {
      disposed = true;
      void load.destroy();
    };
  }, [paper.id, paper.source_version, fileUrl, documentKey]);

  // Keep the page inside a shorter replacement document.
  useEffect(() => {
    if (count && page >= count) setPage(count - 1);
  }, [count, page]);

  // First layout of a document: restore the saved spot or show the current page.
  const placed = useRef("");
  useLayoutEffect(() => {
    if (!doc || !sizes.length || placed.current === docKey) return;
    // Fitting changes the zoom; place the page on the next pass, with the final geometry.
    if (fitWidth && fit(false)) return;
    placed.current = docKey;
    const saved = pending.current;
    if (saved && saved.page === page) {
      scrollToPage(page, saved);
      pending.current = null;
    } else scrollToPage(page);
    reported.current = page;
  }, [doc, sizes.length, docKey, zoom]);

  // A jump from outside (buttons, page box, notes, the coach, search, links).
  useLayoutEffect(() => {
    if (!doc || placed.current !== docKey) return;
    if (page === reported.current) return;
    reported.current = page;
    setFromScroll(false);
    const saved = pending.current;
    if (saved && saved.page === page) {
      scrollToPage(page, saved);
      pending.current = null;
    } else scrollToPage(page, { pdfTop: jumpTop.current });
    jumpTop.current = null;
  }, [page, doc, docKey]);
  const jumpTop = useRef<number | null>(null);
  const jump = useCallback((target: number, top: number | null = null) => {
    if (target === latest.current.page) scrollToPage(target, { pdfTop: top });
    else {
      jumpTop.current = top;
      setPage(target);
    }
  }, [setPage]);

  // --- Scrolling ---------------------------------------------------------------------------
  function updateRange() {
    const box = scroller.current, l = latest.current.layout;
    if (!box || !stack.current || !l.tops.length) return;
    const origin = stackOrigin();
    const top = box.scrollTop - origin.top, h = box.clientHeight;
    const next: [number, number] = [pageAt(top - h * 0.75), pageAt(top + h * 1.75)];
    setRange((r) => (r[0] === next[0] && r[1] === next[1] ? r : next));
  }
  const frame = useRef(0);
  function onScroll() {
    cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(() => {
      const box = scroller.current;
      if (!box || !stack.current || !latest.current.layout.tops.length) return;
      updateRange();
      if (programmatic.current !== null && Math.abs(box.scrollTop - programmatic.current) < 2) return;
      programmatic.current = null;
      pending.current = null;
      const origin = stackOrigin();
      const current = pageAt(box.scrollTop - origin.top + box.clientHeight * READING_LINE);
      if (current !== reported.current) {
        reported.current = current;
        setFromScroll(true);
        setPage(current, "scroll");
      }
      save();
    });
  }
  useEffect(() => () => cancelAnimationFrame(frame.current), []);
  useEffect(updateRange, [layout]);

  // --- Zoom --------------------------------------------------------------------------------
  // A zoom keeps one point fixed on screen: the gesture's centre or the middle of the view.
  const zoomAnchor = useRef<{ page: number; x: number; y: number; clientX: number; clientY: number } | null>(null);
  function changeZoom(next: number, focus?: ZoomFocus, keepFit = false) {
    const box = scroller.current, { zoom: z, layout: l } = latest.current;
    const bounded = boundZoom(next);
    if (box && stack.current && l.tops.length) {
      const origin = stackOrigin();
      const clientX = focus?.clientX ?? origin.box.left + box.clientWidth / 2;
      const clientY = focus?.clientY ?? origin.box.top + box.clientHeight * READING_LINE;
      // Stack-relative point under the focus, at the old zoom.
      const sx = focus ? focus.x * z : box.scrollLeft + clientX - origin.box.left - origin.left;
      const sy = focus ? focus.y * z : box.scrollTop + clientY - origin.box.top - origin.top;
      const p = pageAt(sy);
      zoomAnchor.current = { page: p, x: sx / z, y: (sy - l.tops[p]) / z, clientX, clientY };
    }
    if (!keepFit) setFitWidth(false);
    setZoom(bounded);
  }
  useLayoutEffect(() => {
    const a = zoomAnchor.current, box = scroller.current;
    if (!a || !box || !stack.current) return;
    zoomAnchor.current = null;
    const origin = stackOrigin();
    box.scrollLeft = origin.left + a.x * zoom - (a.clientX - origin.box.left);
    box.scrollTop = origin.top + layout.tops[a.page] + a.y * zoom - (a.clientY - origin.box.top);
    programmatic.current = box.scrollTop;
    updateRange();
    save();
  }, [zoom]);
  const { displayZoom, suppressSelectionUntil } = usePdfZoom({
    scroller, frame: stack, zoom, ready: !!doc && readyPages.has(page),
    documentKey: docKey,
    onCommit: changeZoom,
  });
  /** Fit the widest page to the view. Returns true when the zoom changes. */
  function fit(keep = true) {
    const box = scroller.current, widest = Math.max(0, ...latest.current.sizes.map((s) => s.width));
    if (!box || !widest) return false;
    const style = getComputedStyle(box);
    const width = box.clientWidth - parseFloat(style.paddingLeft || "0") - parseFloat(style.paddingRight || "0");
    if (width <= 0) return false;
    const next = boundZoom(width / widest);
    if (Math.abs(next - latest.current.zoom) <= 0.005) return false;
    if (keep) changeZoom(next, undefined, true);
    else setZoom(next);
    return true;
  }
  useEffect(() => {
    if (fitRequest) {
      setFitWidth(true);
      fit();
    }
  }, [fitRequest]);
  useEffect(() => {
    if (!fitWidth || !scroller.current || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => fit());
    observer.observe(scroller.current);
    return () => observer.disconnect();
  }, [fitWidth, doc]);

  // --- Page callbacks (stable, so pages re-render only when their own data changes) -------------
  const onBaseSize = useCallback((index: number, width: number, height: number) => {
    setSizes((all) => {
      const old = all[index];
      if (!old || (Math.abs(old.width - width) < 0.5 && Math.abs(old.height - height) < 0.5)) return all;
      // A page above the reading line changed height: keep the text under the eye still.
      const box = scroller.current;
      if (box && index < latest.current.page) box.scrollTop += (height - old.height) * latest.current.zoom;
      const next = all.slice();
      next[index] = { width, height };
      return next;
    });
  }, []);
  const onReady = useCallback((index: number, v: Viewport | null) => {
    viewports.current[index] = v;
    setReadyPages((all) => {
      if (all.has(index) === !!v) return all;
      const next = new Set(all);
      if (v) next.add(index); else next.delete(index);
      return next;
    });
  }, []);
  const onScan = useCallback((index: number, empty: boolean) => {
    setScanPages((all) => {
      if (all.has(index) === empty) return all;
      const next = new Set(all);
      if (empty) next.add(index); else next.delete(index);
      return next;
    });
  }, []);

  // --- Selection and regions -------------------------------------------------------------------
  function coords(index: number, element: HTMLElement, rect: { left: number; top: number; right: number; bottom: number }) {
    const b = element.getBoundingClientRect(), v = viewports.current[index]!;
    const p1 = v.convertToPdfPoint(rect.left - b.left, rect.top - b.top),
      p2 = v.convertToPdfPoint(rect.right - b.left, rect.bottom - b.top);
    return [Math.min(p1[0], p2[0]), Math.min(p1[1], p2[1]), Math.max(p1[0], p2[0]), Math.max(p1[1], p2[1])];
  }
  function selectionAnchor(index: number, extra: any) {
    const local = { page_index: index, page_label: labels.current?.[index] || "", quote: "", rects: [], ...extra };
    return derived && rendition
      ? anchorFor(paper, index, { page_index: null, status: "unresolved", rendition: { ...rendition, ...local } })
      : anchorFor(paper, index, local);
  }
  function selected() {
    if (region || Date.now() < suppressSelectionUntil.current || (derived && !rendition)) return;
    const s = window.getSelection();
    if (!s?.rangeCount || !s.toString().trim()) return;
    const start = (s.anchorNode instanceof Element ? s.anchorNode : s.anchorNode?.parentElement)?.closest<HTMLElement>(".pdf-page");
    const end = (s.focusNode instanceof Element ? s.focusNode : s.focusNode?.parentElement)?.closest<HTMLElement>(".pdf-page");
    // A note anchors to one page; a selection that crosses pages is left alone.
    if (!start || start !== end || !start.querySelector(".textLayer")?.contains(s.anchorNode)) return;
    const index = Number(start.dataset.slot);
    if (!viewports.current[index]) return;
    const b = start.getBoundingClientRect();
    const rects = Array.from(s.getRangeAt(0).getClientRects())
      .filter((r) => r.width > 1 && r.height > 1 && r.left >= b.left - 1 && r.right <= b.right + 1 && r.top >= b.top - 1 && r.bottom <= b.bottom + 1)
      .slice(0, 200)
      .map((r) => coords(index, start, r));
    if (rects.length) {
      const box = s.getRangeAt(0).getBoundingClientRect();
      onAnchor(selectionAnchor(index, { quote: s.toString(), rects }), { x: box.left, y: box.bottom + 8 });
    }
  }
  const onRegion = useCallback((index: number, rect: any, element: HTMLElement) => {
    if (!viewports.current[index]) return;
    latestRegion.current(index, rect, element);
  }, []);
  const latestRegion = useRef((_i: number, _r: any, _e: HTMLElement) => {});
  latestRegion.current = (index, rect, element) => {
    onAnchor(selectionAnchor(index, { rects: [coords(index, element, rect)] }), { x: rect.left, y: rect.bottom + 8 });
    setRegion(false);
  };

  // --- What each page draws ------------------------------------------------------------------
  const visible = (a: any) => ((!derived || rendition) ? visibleAnchor(a, paper, rendition) : null);
  const notesByPage = useMemo(() => {
    const map = new Map<number, { id: string; rects: number[][]; rectangle: boolean }[]>();
    for (const n of notes) {
      if (n.paper_id !== paper.id) continue;
      const a = visible(n.anchor);
      if (!a || a.page_index == null || !a.rects?.length) continue;
      const list = map.get(a.page_index) || [];
      list.push({ id: n.id, rects: a.rects, rectangle: n.annotation_type === "rectangle" || !((n.anchor.rendition || n.anchor).quote) });
      map.set(a.page_index, list);
    }
    return map;
  }, [notes, paper.id, paper.source_version, derived, rendition?.job_id, rendition?.view, rendition?.document_version]);
  const pageNotes = notes.filter((n) => n.paper_id === paper.id && (!derived || !!rendition) && visibleAnchor(n.anchor, paper, rendition)?.page_index === page);
  const focus = useMemo(() => {
    const a = visible(focusAnchor);
    return a && a.page_index != null ? { page: a.page_index as number, rects: (a.rects || []) as number[][] } : null;
  }, [focusAnchor, paper.id, paper.source_version, derived, rendition?.job_id]);
  const draft = useMemo(() => {
    const a = visible(draftAnchor);
    return a && a.page_index != null ? { page: a.page_index as number, rects: (a.rects || []) as number[][] } : null;
  }, [draftAnchor, paper.id, paper.source_version, derived, rendition?.job_id]);

  const active = (i: number) => (i >= range[0] - 1 && i <= range[1] + 1) || Math.abs(i - page) <= 1;
  const scan = scanPages.has(page);

  const notesPanel = (
    <>
      <PdfNavigation
        doc={doc}
        sourceKey={paper.id + ":" + paper.source_version}
        page={page}
        fromScroll={fromScroll}
        onNavigate={(p) => jump(p)}
        onSearch={setSearchTerm}
      />
      {scan && (
        <div className="notice">
          这一页没有可提取文字。可以框选图表或扫描文字，在教练对话中附上整页图像一起阅读。
        </div>
      )}
      {!!pageNotes.length && (
        <details className="reader-annotations">
          <summary>本页批注 · {pageNotes.length}</summary>
          <div>
            {pageNotes.map((n) => (
              <button key={n.id} onClick={() => onLocateNote?.(n.anchor)} title={n.content}>
                <b>
                  {n.author === "assistant" ? "AI 评论" : n.author === "external" ? "Zotero 笔记" : "我的原话"}
                  {n.read_only ? " · 只读" : ""}
                </b>
                <span>{n.content}</span>
              </button>
            ))}
          </div>
        </details>
      )}
    </>
  );

  return (
    <div
      className="reader"
      tabIndex={0}
      aria-label="PDF 阅读器"
      onKeyDown={(e) => {
        if (e.target instanceof HTMLElement && e.target.closest("input,textarea,select,button,[contenteditable=true]")) return;
        if (e.key === "Escape") setRegion(false);
        if (e.ctrlKey || e.metaKey || e.altKey || e.shiftKey) return;
        if (e.key === "ArrowLeft" && page > 0) {
          e.preventDefault();
          jump(page - 1);
        }
        if (e.key === "ArrowRight" && page < (count || paper.page_count) - 1) {
          e.preventDefault();
          jump(page + 1);
        }
      }}
    >
      {toolsContainer ? createPortal(<div className="pdf-tools-content">{notesPanel}</div>, toolsContainer) : notesPanel}
      <div className="pdf-stage">
        <div className="pdf-scroll" ref={scroller} onScroll={onScroll}>
          {error && (
            <div className="notice" role="alert">
              {error}
            </div>
          )}
          {!doc ? (
            !error && <div className="empty">正在打开论文…</div>
          ) : (
            <div
              ref={stack}
              className="pdf-stack"
              style={{ width: layout.width, height: layout.height }}
              onMouseUp={selected}
              onKeyUp={selected}
              onTouchEnd={() => window.setTimeout(selected, 200)}
            >
              {sizes.map((s, i) => (
                <PdfPage
                  key={docKey + ":" + i}
                  doc={doc}
                  index={i}
                  zoom={zoom}
                  width={s.width * zoom}
                  height={s.height * zoom}
                  active={active(i)}
                  paperId={paper.id}
                  sourceVersion={derived ? documentKey : paper.source_version}
                  derived={derived ? documentKey : undefined}
                  notes={notesByPage.get(i) || NONE}
                  focusRects={focus?.page === i ? focus.rects : NONE}
                  draftRects={draft?.page === i ? draft.rects : NONE}
                  marks={!derived && coachMarks?.page_index === i ? coachMarks.marks : NONE}
                  region={region}
                  searchTerm={searchTerm}
                  onBaseSize={onBaseSize}
                  onReady={onReady}
                  onScan={onScan}
                  onRegion={onRegion}
                  onLink={jump}
                  suppressUntil={suppressSelectionUntil}
                />
              ))}
            </div>
          )}
        </div>
        <div className="pdf-floating-tools" role="toolbar" aria-label="PDF 快捷工具">
          {onViewChange && <select className="pdf-view-select" aria-label="PDF 阅读视图" title="切换原文、中文或双语；译文生成后可用" value={view} onChange={(e) => onViewChange(e.target.value as "original" | "mono" | "dual")}>
            <option value="original">原文</option>
            <option value="mono" disabled={!availableViews?.mono}>中文</option>
            <option value="dual" disabled={!availableViews?.dual}>双语</option>
          </select>}
          <button title="放大 · 也可以双指缩放或按住 Ctrl 滚动" aria-label="PDF 放大" disabled={!doc || displayZoom >= MAX_ZOOM} onClick={() => changeZoom(zoom + .15)}><ZoomIn size={17} /></button>
          <output aria-label="PDF 缩放比例">{Math.round(displayZoom * 100)}%</output>
          <button title="缩小" aria-label="PDF 缩小" disabled={!doc || displayZoom <= MIN_ZOOM} onClick={() => changeZoom(zoom - .15)}><ZoomOut size={17} /></button>
          <button title="适应宽度" aria-label="PDF 适应宽度" aria-pressed={fitWidth} disabled={!doc} onClick={() => { setFitWidth(true); fit(); }}><Maximize size={16} /></button>
          <span className="pdf-tool-divider" />
          <PageNavigation page={page} count={count} onChange={(p) => jump(p)} labelPrefix="PDF " />
          <span className="pdf-tool-divider" />
          <button title="框选区域" aria-label="PDF 框选区域" aria-pressed={region} disabled={!doc || (derived && !rendition)} onClick={() => setRegion(!region)}><Scan size={17} /></button>
          {onExport && <button title="下载当前 PDF（含批注）" aria-label="下载当前 PDF（含批注）" disabled={!doc || exporting || (derived && !rendition)} onClick={onExport}><Download size={17} /></button>}
        </div>
      </div>
      {!toolsContainer && (
        <div className="reader-footer">
          选中文字或框选区域，让想法有出处。原始 PDF 保持完整。
        </div>
      )}
    </div>
  );
}

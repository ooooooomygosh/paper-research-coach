import PageNavigation from "./PageNavigation";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  getDocument,
  GlobalWorkerOptions,
  TextLayer,
  type PDFDocumentProxy,
  type PDFPageProxy,
} from "pdfjs-dist/legacy/build/pdf.mjs";
// The legacy build polyfills very recent APIs (e.g. Map#getOrInsertComputed,
// Math.sumPrecise) that the modern pdf.js 6 build calls unconditionally; without
// it, pages fail to render in browsers that are only a few months old.
import worker from "pdfjs-dist/legacy/build/pdf.worker.min.mjs?url";
import "./pdf-text-layer.css";
import "./reading-experience.css";
import "./pdf-controls.css";
import { boundZoom, MIN_ZOOM, MAX_ZOOM, usePdfZoom, type ZoomFocus } from "./usePdfZoom";
import {
  MousePointer2,
  Scan,
  ZoomIn,
  ZoomOut,
  Download,
  Maximize,
} from "lucide-react";
import { anchorFor, visibleAnchor, type Row } from "./api";
import PdfNavigation from "./PdfNavigation";
GlobalWorkerOptions.workerSrc = worker;
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
}: {
  paper: Row;
  page: number;
  setPage: (n: number) => void;
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
}) {
  const canvas = useRef<HTMLCanvasElement>(null),
    layer = useRef<HTMLDivElement>(null),
    frame = useRef<HTMLDivElement>(null),
    viewport = useRef<ReturnType<PDFPageProxy["getViewport"]> | null>(null);
  const [doc, setDoc] = useState<PDFDocumentProxy | null>(null),
    [error, setError] = useState(""),
    [zoom, setZoom] = useState(1.1),
    [size, setSize] = useState({ width: 620, height: 800 }),
    [region, setRegion] = useState(false),
    [drag, setDrag] = useState<any>(null),
    [scan, setScan] = useState(false),
    [rendered, setRendered] = useState("");
  const labels = useRef<string[] | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const [fitWidth, setFitWidth] = useState(true);
  const positionKey = "prc-viewport-" + paper.id + ":" + paper.source_version + (documentKey === "original" ? "" : ":" + documentKey);
  const savedScroll = useRef({ top: 0, left: 0 });
  const restoredPage = useRef<number | null>(null);
  const restoring = useRef(true);
  const renderKey =
    paper.id + ":" + paper.source_version + ":" + documentKey + ":" + page + ":" + zoom;
  const zoomFocus = useRef<ZoomFocus | null>(null);
  function changeZoom(next: number, focus?: ZoomFocus) {
    const box = scroller.current, sheet = frame.current;
    if (!focus && box && sheet) {
      const b = box.getBoundingClientRect(), f = sheet.getBoundingClientRect();
      const clientX = b.left + b.width / 2, clientY = b.top + b.height / 2;
      focus = { x: (clientX - f.left) / zoom, y: (clientY - f.top) / zoom, clientX, clientY };
    }
    zoomFocus.current = focus || null;
    setFitWidth(false);
    setZoom(boundZoom(next));
  }
  const { displayZoom, suppressSelectionUntil } = usePdfZoom({
    scroller, frame, zoom, ready: !!doc && rendered === renderKey,
    documentKey: paper.id + ":" + paper.source_version + ":" + documentKey,
    onCommit: changeZoom,
  });
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(positionKey) || "{}");
      setFitWidth(saved.fit !== false);
      if (Number.isFinite(saved.zoom))
        setZoom(boundZoom(saved.zoom));
      savedScroll.current = {
        top: Number(saved.top) || 0,
        left: Number(saved.left) || 0,
      };
      restoredPage.current = Number.isInteger(saved.page) ? saved.page : null;
    } catch {
      savedScroll.current = { top: 0, left: 0 };
    }
    restoring.current = true;
  }, [positionKey]);
  useEffect(() => {
    restoring.current = true;
  }, [documentKey]);
  const lastPosition = useRef({ key: positionKey, page });
  useEffect(() => {
    const loadingSavedPage = restoredPage.current === page;
    if (
      lastPosition.current.key === positionKey &&
      lastPosition.current.page !== page &&
      !loadingSavedPage
    ) {
      savedScroll.current = { top: 0, left: 0 };
      restoring.current = true;
    }
    if (loadingSavedPage) restoredPage.current = null;
    lastPosition.current = { key: positionKey, page };
  }, [page, positionKey]);
  useEffect(() => {
    if (fitRequest) {
      setFitWidth(true);
      fit();
    }
  }, [fitRequest]);
  function rememberScroll() {
    const box = scroller.current;
    if (!box || restoring.current || rendered !== renderKey) return;
    savedScroll.current = {
      top: box.scrollTop / Math.max(1, box.scrollHeight - box.clientHeight),
      left: box.scrollLeft / Math.max(1, box.scrollWidth - box.clientWidth),
    };
    localStorage.setItem(
      positionKey,
      JSON.stringify({ ...savedScroll.current, zoom, fit: fitWidth, page }),
    );
  }
  useEffect(() => {
    if (rendered !== renderKey || !scroller.current) return;
    if (zoomFocus.current && frame.current) {
      const focus = zoomFocus.current, b = frame.current.getBoundingClientRect();
      const box = scroller.current;
      box.scrollLeft += b.left + focus.x * zoom - focus.clientX;
      box.scrollTop += b.top + focus.y * zoom - focus.clientY;
      zoomFocus.current = null;
      restoring.current = false;
      rememberScroll();
      return;
    }
    if (fitWidth) fit();
    if (restoring.current) {
      const box = scroller.current;
      box.scrollTop =
        savedScroll.current.top *
        Math.max(0, box.scrollHeight - box.clientHeight);
      box.scrollLeft =
        savedScroll.current.left *
        Math.max(0, box.scrollWidth - box.clientWidth);
      restoring.current = false;
    }
    localStorage.setItem(
      positionKey,
      JSON.stringify({ ...savedScroll.current, zoom, fit: fitWidth, page }),
    );
  }, [rendered, zoom, fitWidth]);
  function fit() {
    const v = viewport.current,
      box = scroller.current;
    if (!v || !box) return;
    const style = getComputedStyle(box);
    const width =
      box.clientWidth -
      parseFloat(style.paddingLeft || "0") -
      parseFloat(style.paddingRight || "0");
    if (width > 0) {
      const next = boundZoom((width * v.scale) / v.width);
      if (Math.abs(next - zoom) > 0.005) {
        restoring.current = true;
        setZoom(next);
      }
    }
  }
  useEffect(() => {
    if (!fitWidth || !scroller.current || typeof ResizeObserver === "undefined")
      return;
    const observer = new ResizeObserver(fit);
    observer.observe(scroller.current);
    return () => observer.disconnect();
  }, [fitWidth, zoom, rendered]);
  const pageNotes = notes.filter(
    (n) =>
      n.paper_id === paper.id &&
      (!derived || !!rendition) &&
      visibleAnchor(n.anchor, paper, rendition)?.page_index === page,
  );
  function highlightStyle(r: number[]) {
    const v = viewport.current;
    if (!v || r.length !== 4 || !r.every(Number.isFinite)) return undefined;
    const [x0, y0] = v.convertToViewportPoint(r[0], r[1]);
    const [x1, y1] = v.convertToViewportPoint(r[2], r[3]);
    return {
      left: Math.min(x0, x1),
      top: Math.min(y0, y1),
      width: Math.abs(x1 - x0),
      height: Math.abs(y1 - y0),
    };
  }
  useEffect(() => {
    let disposed = false;
    setDoc(null);
    setError("");
    viewport.current = null;
    setScan(false);
    setRendered("");
    setDrag(null);
    setRegion(false);
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
        if (disposed) return;
        labels.current = pageLabels;
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
  useEffect(() => {
    if (!doc || !canvas.current || !layer.current) return;
    const bounded = Math.max(0, Math.min(page, doc.numPages - 1));
    if (bounded !== page) {
      setPage(bounded);
      return;
    }
    setError("");
    viewport.current = null;
    setRendered("");
    layer.current.replaceChildren();
    let disposed = false,
      render: any,
      text: any;
    doc
      .getPage(page + 1)
      .then(async (p) => {
        if (disposed) return;
        const v = p.getViewport({ scale: zoom });
        viewport.current = null;
        setSize({ width: v.width, height: v.height });
        const c = canvas.current!;
        // Bound raster memory for wide bilingual pages at high zoom.
        const pixelRatio = Math.min(devicePixelRatio, Math.sqrt(16_000_000 / (v.width * v.height)));
        c.width = v.width * pixelRatio;
        c.height = v.height * pixelRatio;
        c.style.width = v.width + "px";
        c.style.height = v.height + "px";
        render = p.render({
          canvas: c,
          viewport: v,
          transform: [pixelRatio, 0, 0, pixelRatio, 0, 0],
        });
        // Cancellation may happen while text content is still loading.
        void render.promise.catch(() => {});
        const content = await p.getTextContent();
        if (disposed) return;
        setScan(!content.items.length);
        layer.current!.replaceChildren();
        layer.current!.style.setProperty("--total-scale-factor", String(zoom));
        text = new TextLayer({
          textContentSource: content,
          container: layer.current!,
          viewport: v,
        });
        await Promise.all([text.render(), render.promise]);
        if (!disposed) {
          viewport.current = v;
          setRendered(renderKey);
        }
      })
      .catch((e) => {
        if (disposed || e.name === "RenderingCancelledException") return;
        console.warn("PDF page render failed", e);
        setError("此页无法显示，请尝试其他页。");
      });
    return () => {
      disposed = true;
      render?.cancel();
      text?.cancel();
    };
  }, [doc, page, zoom, paper.id, paper.source_version, documentKey]);
  function coords(
    rect:
      DOMRect | { left: number; top: number; right: number; bottom: number },
  ) {
    const b = frame.current!.getBoundingClientRect(),
      v = viewport.current!;
    const p1 = v.convertToPdfPoint(rect.left - b.left, rect.top - b.top),
      p2 = v.convertToPdfPoint(rect.right - b.left, rect.bottom - b.top);
    return [
      Math.min(p1[0], p2[0]),
      Math.min(p1[1], p2[1]),
      Math.max(p1[0], p2[0]),
      Math.max(p1[1], p2[1]),
    ];
  }
  function selectionAnchor(extra: any) {
    const local = { page_index: page, page_label: labels.current?.[page] || "", quote: "", rects: [], ...extra };
    return derived && rendition
      ? anchorFor(paper, page, { page_index: null, status: "unresolved", rendition: { ...rendition, ...local } })
      : anchorFor(paper, page, local);
  }
  function selected() {
    if (region || !viewport.current || rendered !== renderKey || Date.now() < suppressSelectionUntil.current || (derived && !rendition)) return;
    const s = window.getSelection();
    if (
      !s?.rangeCount ||
      !s.toString().trim() ||
      !layer.current?.contains(s.anchorNode) ||
      !layer.current?.contains(s.focusNode)
    )
      return;
    const b = frame.current!.getBoundingClientRect();
    const rects = Array.from(s.getRangeAt(0).getClientRects())
      .filter(
        (r) =>
          r.width > 1 &&
          r.height > 1 &&
          r.left >= b.left - 1 &&
          r.right <= b.right + 1 &&
          r.top >= b.top - 1 &&
          r.bottom <= b.bottom + 1,
      )
      .slice(0, 200)
      .map(coords);
    if (rects.length)
      onAnchor(
        selectionAnchor({
          quote: s.toString(),
          rects,
          page_label: labels.current?.[page] || "",
        }),
        {
          x: s.getRangeAt(0).getBoundingClientRect().left,
          y: s.getRangeAt(0).getBoundingClientRect().bottom + 8,
        },
      );
  }
  function regionEnd(e: React.PointerEvent) {
    if (!drag || !viewport.current || rendered !== renderKey || Date.now() < suppressSelectionUntil.current) return;
    const b = frame.current!.getBoundingClientRect();
    const x = Math.max(0, Math.min(e.clientX - b.left, b.width)),
      y = Math.max(0, Math.min(e.clientY - b.top, b.height));
    if (Math.abs(x - drag.x) > 3 && Math.abs(y - drag.y) > 3)
      onAnchor(
        selectionAnchor({
          rects: [
            coords({
              left: b.left + Math.min(x, drag.x),
              right: b.left + Math.max(x, drag.x),
              top: b.top + Math.min(y, drag.y),
              bottom: b.top + Math.max(y, drag.y),
            }),
          ],
          page_label: labels.current?.[page] || "",
        }),
        { x: b.left + Math.min(x, drag.x), y: b.top + Math.max(y, drag.y) + 8 },
      );
    setDrag(null);
    setRegion(false);
  }
  const visibleFocus = (!derived || rendition) && visibleAnchor(focusAnchor, paper, rendition);
  const focused = rendered === renderKey && visibleFocus?.page_index === page ? visibleFocus.rects || [] : [];
  const visibleDraft = (!derived || rendition) && visibleAnchor(draftAnchor, paper, rendition);
  useEffect(() => {
    if (
      rendered === renderKey &&
      visibleFocus?.page_index === page
    ) {
      frame.current
        ?.querySelector(".anchor-highlight")
        ?.scrollIntoView({ block: "center", inline: "center" });
    }
  }, [focusAnchor, rendered, page, paper.source_version, documentKey]);
  return (
    <div
      className="reader"
      tabIndex={0}
      aria-label="PDF 阅读器"
      onKeyDown={(e) => {
        if (
          e.target instanceof HTMLElement &&
          e.target.closest(
            "input,textarea,select,button,[contenteditable=true]",
          )
        )
          return;
        if (e.key === "Escape") {
          setDrag(null);
          setRegion(false);
        }
        if (e.ctrlKey || e.metaKey || e.altKey || e.shiftKey) return;
        if (e.key === "ArrowLeft" && page > 0) {
          e.preventDefault();
          setPage(page - 1);
        }
        if (
          e.key === "ArrowRight" &&
          page < (doc?.numPages ?? paper.page_count) - 1
        ) {
          e.preventDefault();
          setPage(page + 1);
        }
      }}
    >
      {toolsContainer ? (
        createPortal(
          <div className="pdf-tools-content">
            {" "}
<PdfNavigation
              doc={doc}
              sourceKey={paper.id + ":" + paper.source_version}
              page={page}
              onNavigate={setPage}
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
                    <button
                      key={n.id}
                      onClick={() => onLocateNote?.(n.anchor)}
                      title={n.content}
                    >
                      <b>
                        {n.author === "assistant"
                          ? "AI 评论"
                          : n.author === "external"
                            ? "Zotero 笔记"
                            : "我的原话"}
                        {n.read_only ? " · 只读" : ""}
                      </b>
                      <span>{n.content}</span>
                    </button>
                  ))}
                </div>
              </details>
            )}
          </div>,
          toolsContainer,
        )
      ) : (
        <>
          {" "}
<PdfNavigation
            doc={doc}
            sourceKey={paper.id + ":" + paper.source_version}
            page={page}
            onNavigate={setPage}
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
                  <button
                    key={n.id}
                    onClick={() => onLocateNote?.(n.anchor)}
                    title={n.content}
                  >
                    <b>
                      {n.author === "assistant"
                        ? "AI 评论"
                        : n.author === "external"
                          ? "Zotero 笔记"
                          : "我的原话"}
                      {n.read_only ? " · 只读" : ""}
                    </b>
                    <span>{n.content}</span>
                  </button>
                ))}
              </div>
            </details>
          )}
        </>
      )}
      <div className="pdf-stage">
      <div className="pdf-scroll" ref={scroller} onScroll={rememberScroll}>
        {error && (
          <div className="notice" role="alert">
            {error}
          </div>
        )}
        {!doc ? (
          !error && <div className="empty">正在打开论文…</div>
        ) : (
          <div
            ref={frame}
            className="pdf-page"
            data-paper-id={paper.id}
            data-source-version={derived ? documentKey : paper.source_version}
            data-derived={derived ? documentKey : undefined}
            data-page-index={rendered === renderKey ? page : -1}
            style={size}
            onMouseUp={selected}
            onKeyUp={selected}
            onTouchEnd={() => window.setTimeout(selected, 200)}
          >
            <canvas ref={canvas} />
            <div ref={layer} className="textLayer" />
            {rendered === renderKey &&
              pageNotes.flatMap((n) =>
                (visibleAnchor(n.anchor, paper, rendition)?.rects || []).map((r: number[], i: number) => {
                  const style = highlightStyle(r);
                  return style ? (
                    <div
                      key={n.id + ":" + i}
                      className={"saved-annotation" + (n.annotation_type === "rectangle" || !((n.anchor.rendition || n.anchor).quote) ? " rectangle" : "")}
                      data-note-id={n.id}
                      aria-hidden="true"
                      style={style}
                    />
                  ) : null;
                }),
              )}
            {rendered === renderKey && visibleDraft?.page_index === page && (visibleDraft.rects || []).map((r: number[], i: number) => (
              <div key={i} className="draft-annotation" aria-hidden="true" style={highlightStyle(r)} />
            ))}
            {focused.map((r: number[], i: number) => {
              const v = viewport.current;
              if (!v) return null;
              const [x0, y0] = v.convertToViewportPoint(r[0], r[1]);
              const [x1, y1] = v.convertToViewportPoint(r[2], r[3]);
              return (
                <div
                  key={i}
                  className="anchor-highlight"
                  style={{
                    left: Math.min(x0, x1),
                    top: Math.min(y0, y1),
                    width: Math.abs(x1 - x0),
                    height: Math.abs(y1 - y0),
                  }}
                />
              );
            })}
            {region && (
              <div
                className="region-layer"
                onPointerDown={(e) => {
                  if (!e.isPrimary || Date.now() < suppressSelectionUntil.current) { setDrag(null); return; }
                  e.currentTarget.setPointerCapture(e.pointerId);
                  const b = frame.current!.getBoundingClientRect();
                  setDrag({
                    x: e.clientX - b.left,
                    y: e.clientY - b.top,
                    x2: e.clientX - b.left,
                    y2: e.clientY - b.top,
                  });
                }}
                onPointerMove={(e) => {
                  if (drag) {
                    const b = frame.current!.getBoundingClientRect();
                    setDrag({
                      ...drag,
                      x2: e.clientX - b.left,
                      y2: e.clientY - b.top,
                    });
                  }
                }}
                onPointerUp={regionEnd}
                onPointerCancel={() => setDrag(null)}
                onLostPointerCapture={() => setDrag(null)}
              >
                {drag && (
                  <div
                    className="region-box"
                    style={{
                      left: Math.min(drag.x, drag.x2),
                      top: Math.min(drag.y, drag.y2),
                      width: Math.abs(drag.x - drag.x2),
                      height: Math.abs(drag.y - drag.y2),
                    }}
                  />
                )}
              </div>
            )}
          </div>
        )}
      </div>
      <div className="pdf-floating-tools" role="toolbar" aria-label="PDF 快捷工具">
        {onViewChange && <select className="pdf-view-select" aria-label="PDF 阅读视图" title="切换原文、中文或双语；译文生成后可用" value={view} onChange={(e) => onViewChange(e.target.value as "original" | "mono" | "dual")}>
          <option value="original">原文</option>
          <option value="mono" disabled={!availableViews?.mono}>中文</option>
          <option value="dual" disabled={!availableViews?.dual}>双语</option>
        </select>}
        <button title="放大 · 支持双指缩放" aria-label="PDF 放大" disabled={!doc || displayZoom >= MAX_ZOOM} onClick={() => changeZoom(zoom + .15)}><ZoomIn size={17} /></button>
        <output aria-label="PDF 缩放比例">{Math.round(displayZoom * 100)}%</output>
        <button title="缩小" aria-label="PDF 缩小" disabled={!doc || displayZoom <= MIN_ZOOM} onClick={() => changeZoom(zoom - .15)}><ZoomOut size={17} /></button>
        <button title="适应宽度" aria-label="PDF 适应宽度" aria-pressed={fitWidth} disabled={!doc} onClick={() => { zoomFocus.current = null; setFitWidth(true); fit(); }}><Maximize size={16} /></button>
        <span className="pdf-tool-divider" />
        <PageNavigation page={page} count={doc?.numPages || 0} onChange={setPage} labelPrefix="PDF " />
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

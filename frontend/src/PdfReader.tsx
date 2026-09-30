import { useEffect, useRef, useState } from "react";
import {
  getDocument,
  GlobalWorkerOptions,
  TextLayer,
  type PDFDocumentProxy,
  type PDFPageProxy,
} from "pdfjs-dist";
import worker from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import "./pdf-text-layer.css";
import {
  ChevronLeft,
  ChevronRight,
  MousePointer2,
  Scan,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { anchorFor, type Row } from "./api";
GlobalWorkerOptions.workerSrc = worker;
export default function PdfReader({
  paper,
  page,
  setPage,
  onAnchor,
  focusAnchor,
}: {
  paper: Row;
  page: number;
  setPage: (n: number) => void;
  onAnchor: (a: any) => void;
  focusAnchor: any;
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
  useEffect(() => {
    let disposed = false;
    setDoc(null);
    setError("");
    viewport.current = null;
    setScan(false);
    const load = getDocument({
      url: "/api/pdf/" + paper.id,
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
      .catch(() => {
        if (!disposed)
          setError("PDF 暂不可用。请检查文件位置；换版后需要重新确认锚点。");
      });
    return () => {
      disposed = true;
      void load.destroy();
    };
  }, [paper.id, paper.source_version]);
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
        c.width = v.width * devicePixelRatio;
        c.height = v.height * devicePixelRatio;
        c.style.width = v.width + "px";
        c.style.height = v.height + "px";
        render = p.render({
          canvas: c,
          viewport: v,
          transform: [devicePixelRatio, 0, 0, devicePixelRatio, 0, 0],
        });
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
          setRendered(paper.source_version + ":" + page);
        }
      })
      .catch((e) => {
        if (!disposed && e.name !== "RenderingCancelledException")
          setError("此页无法显示，请尝试其他页。");
      });
    return () => {
      disposed = true;
      render?.cancel();
      text?.cancel();
    };
  }, [doc, page, zoom]);
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
  function selected() {
    if (
      region ||
      !viewport.current ||
      rendered !== paper.source_version + ":" + page
    )
      return;
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
        anchorFor(paper, page, {
          quote: s.toString(),
          rects,
          page_label: labels.current?.[page] || "",
        }),
      );
  }
  function regionEnd(e: React.PointerEvent) {
    if (
      !drag ||
      !viewport.current ||
      rendered !== paper.source_version + ":" + page
    )
      return;
    const b = frame.current!.getBoundingClientRect();
    const x = Math.max(0, Math.min(e.clientX - b.left, b.width)),
      y = Math.max(0, Math.min(e.clientY - b.top, b.height));
    if (Math.abs(x - drag.x) > 3 && Math.abs(y - drag.y) > 3)
      onAnchor(
        anchorFor(paper, page, {
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
      );
    setDrag(null);
    setRegion(false);
  }
  const focused =
    rendered === paper.source_version + ":" + page &&
    focusAnchor?.status === "verified" &&
    focusAnchor.source_version === paper.source_version &&
    focusAnchor.page_index === page
      ? focusAnchor.rects || []
      : [];
  useEffect(() => {
    if (
      rendered === paper.source_version + ":" + page &&
      focusAnchor?.status === "verified" &&
      focusAnchor.source_version === paper.source_version &&
      focusAnchor.page_index === page
    ) {
      frame.current
        ?.querySelector(".anchor-highlight")
        ?.scrollIntoView({ block: "center", inline: "center" });
    }
  }, [focusAnchor, rendered, page, paper.source_version]);
  return (
    <div className="reader">
      <div className="reader-toolbar">
        <button
          aria-label="上一页"
          disabled={page === 0}
          onClick={() => setPage(page - 1)}
        >
          <ChevronLeft size={17} />
        </button>
        <label>
          第{" "}
          <input
            aria-label="PDF 页码"
            type="number"
            min="1"
            max={paper.page_count || 1}
            value={page + 1}
            onChange={(e) =>
              setPage(
                Math.max(
                  0,
                  Math.min(paper.page_count - 1, Number(e.target.value) - 1),
                ),
              )
            }
          />{" "}
          / {paper.page_count} 页
        </label>
        <button
          aria-label="下一页"
          disabled={page >= paper.page_count - 1}
          onClick={() => setPage(page + 1)}
        >
          <ChevronRight size={17} />
        </button>
        <span className="toolbar-space" />
        <button
          aria-label="缩小"
          onClick={() => setZoom(Math.max(0.5, zoom - 0.15))}
        >
          <ZoomOut size={16} />
        </button>
        <span>{Math.round(zoom * 100)}%</span>
        <button
          aria-label="放大"
          onClick={() => setZoom(Math.min(2.5, zoom + 0.15))}
        >
          <ZoomIn size={16} />
        </button>
        <button
          className={region ? "active" : ""}
          onClick={() => setRegion(!region)}
        >
          {region ? <MousePointer2 size={16} /> : <Scan size={16} />}框选
        </button>
      </div>
      {scan && (
        <div className="notice">
          这一页没有可提取文字。可以框选图表或扫描文字，再在宿主中一起阅读。
        </div>
      )}
      <div className="pdf-scroll">
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
            data-page-index={rendered === paper.source_version + ":" + page ? page : -1}
            style={size}
            onMouseUp={selected}
          >
            <canvas ref={canvas} />
            <div ref={layer} className="textLayer" />
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
      <div className="reader-footer">
        选中文字或框选区域，让想法有出处。原始 PDF 保持完整。
      </div>
    </div>
  );
}

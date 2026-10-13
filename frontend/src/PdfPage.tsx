import { memo, useEffect, useRef, useState } from "react";
import { TextLayer, type PDFDocumentProxy, type PDFPageProxy } from "pdfjs-dist/legacy/build/pdf.mjs";

export type Viewport = ReturnType<PDFPageProxy["getViewport"]>;
export type Mark = { rects: number[][]; n: number; label?: string; current?: boolean };
type Link = { rect: number[]; page?: number; top?: number | null; url?: string };
type ClientRect = { left: number; top: number; right: number; bottom: number };

const SAFE_URL = /^(https?:|mailto:)/i;

/** Resolve a link annotation's destination to a 0-based page and an optional PDF-space top. */
async function linkTarget(doc: PDFDocumentProxy, dest: any): Promise<{ page: number; top: number | null } | null> {
  try {
    const explicit = typeof dest === "string" ? await doc.getDestination(dest) : dest;
    if (!Array.isArray(explicit) || explicit[0] == null) return null;
    const ref = explicit[0];
    const page = typeof ref === "object" ? await doc.getPageIndex(ref) : Number.isInteger(ref) ? ref : null;
    if (page === null || page < 0 || page >= doc.numPages) return null;
    // [ref, {name: "XYZ"}, left, top, zoom] and [ref, {name: "FitH"}, top] carry a top.
    const kind = explicit[1]?.name;
    const top = kind === "XYZ" ? explicit[3] : kind === "FitH" || kind === "FitBH" ? explicit[2] : null;
    return { page, top: Number.isFinite(top) ? top : null };
  } catch {
    return null;
  }
}

/** One page of the scrolling stack. Draws only while `active`; otherwise keeps its size as a placeholder. */
function PdfPage({
  doc, index, zoom, width, height, active, paperId, sourceVersion, derived,
  notes, focusRects, draftRects, marks, region, searchTerm,
  onBaseSize, onReady, onScan, onRegion, onLink, suppressUntil,
}: {
  doc: PDFDocumentProxy;
  index: number;
  zoom: number;
  width: number;
  height: number;
  active: boolean;
  paperId: string;
  sourceVersion: string;
  derived?: string;
  notes: { id: string; rects: number[][]; rectangle: boolean }[];
  focusRects: number[][];
  draftRects: number[][];
  marks: Mark[];
  region: boolean;
  searchTerm: string;
  onBaseSize: (index: number, width: number, height: number) => void;
  onReady: (index: number, viewport: Viewport | null) => void;
  onScan: (index: number, empty: boolean) => void;
  onRegion: (index: number, rect: ClientRect, element: HTMLElement) => void;
  onLink: (page: number, top: number | null) => void;
  suppressUntil: { current: number };
}) {
  const element = useRef<HTMLDivElement>(null);
  const host = useRef<HTMLDivElement>(null);
  const [viewport, setViewport] = useState<Viewport | null>(null);
  const [error, setError] = useState(false);
  const [links, setLinks] = useState<Link[]>([]);
  const [drag, setDrag] = useState<{ x: number; y: number; x2: number; y2: number } | null>(null);

  useEffect(() => {
    if (!active) {
      host.current?.replaceChildren();
      setViewport(null);
      setLinks([]);
      onReady(index, null);
      return;
    }
    let disposed = false, render: any;
    setError(false);
    doc.getPage(index + 1).then(async (p) => {
      if (disposed) return;
      const base = p.getViewport({ scale: 1 });
      onBaseSize(index, base.width, base.height);
      const v = p.getViewport({ scale: zoom });
      // Draw into a fresh canvas and swap it in when done, so zooming never flashes a blank page.
      const canvas = document.createElement("canvas");
      const pixelRatio = Math.min(devicePixelRatio || 1, Math.sqrt(16_000_000 / (v.width * v.height)));
      canvas.width = v.width * pixelRatio;
      canvas.height = v.height * pixelRatio;
      render = p.render({ canvas, viewport: v, transform: [pixelRatio, 0, 0, pixelRatio, 0, 0] });
      void render.promise.catch(() => {});
      const content = await p.getTextContent();
      if (disposed) return;
      onScan(index, !content.items.length);
      const layer = document.createElement("div");
      layer.className = "textLayer";
      layer.style.setProperty("--total-scale-factor", String(zoom));
      const text = new TextLayer({ textContentSource: content, container: layer, viewport: v });
      const annotations: any[] = typeof p.getAnnotations === "function" ? await p.getAnnotations({ intent: "display" }).catch(() => []) : [];
      await Promise.all([text.render(), render.promise]);
      if (disposed) return;
      const found: Link[] = [];
      for (const a of annotations.slice(0, 400)) {
        if (a?.subtype !== "Link" || !Array.isArray(a.rect)) continue;
        if (typeof a.url === "string" && SAFE_URL.test(a.url)) found.push({ rect: a.rect, url: a.url });
        else if (a.dest) {
          const target = await linkTarget(doc, a.dest);
          if (target) found.push({ rect: a.rect, ...target });
        }
      }
      if (disposed) return;
      host.current?.replaceChildren(canvas, layer);
      setLinks(found);
      setViewport(v);
      onReady(index, v);
    }).catch((e) => {
      if (disposed || e?.name === "RenderingCancelledException") return;
      console.warn("PDF page render failed", e);
      setError(true);
    });
    return () => {
      disposed = true;
      // Only the canvas is cancelled: TextLayer.cancel() in pdf.js 6 can throw from a pending
      // stream read, and an unfinished layer is still detached, so it can finish into nothing.
      render?.cancel();
    };
  }, [doc, index, zoom, active]);

  useEffect(() => {
    if (!region) setDrag(null);
  }, [region]);

  useEffect(() => {
    const layer = host.current?.querySelector(".textLayer");
    if (!layer) return;
    const term = searchTerm.trim().toLocaleLowerCase();
    layer.querySelectorAll("span").forEach((span) => {
      span.classList.toggle("search-hit", !!term && term.length > 1 && (span.textContent || "").toLocaleLowerCase().includes(term));
    });
  }, [searchTerm, viewport]);

  // Bring a new highlight or new coach marks into view once; a zoom redraw must not pull the reader back.
  const shown = useRef<unknown>(null);
  useEffect(() => {
    if (!viewport) return;
    const target = focusRects.length ? focusRects : marks.length ? marks : null;
    if (!target || shown.current === target) return;
    shown.current = target;
    element.current?.querySelector(focusRects.length ? ".anchor-highlight" : ".coach-mark")?.scrollIntoView({ block: "center", inline: "nearest" });
  }, [focusRects, marks, viewport]);

  function box(r: number[]) {
    if (!viewport || r.length !== 4 || !r.every(Number.isFinite)) return undefined;
    const [x0, y0] = viewport.convertToViewportPoint(r[0], r[1]);
    const [x1, y1] = viewport.convertToViewportPoint(r[2], r[3]);
    return { left: Math.min(x0, x1), top: Math.min(y0, y1), width: Math.abs(x1 - x0), height: Math.abs(y1 - y0) };
  }

  const ready = !!viewport;
  return (
    <div
      ref={element}
      className="pdf-page"
      data-slot={index}
      data-paper-id={paperId}
      data-source-version={sourceVersion}
      data-derived={derived}
      data-page-index={ready ? index : -1}
      style={{ width, height }}
    >
      <div ref={host} className="pdf-page-raster" />
      {error && <div className="notice pdf-page-error" role="alert">第 {index + 1} 页无法显示。其他页不受影响。</div>}
      {ready && links.map((l, i) => {
        const style = box(l.rect);
        if (!style) return null;
        return l.url ? (
          <a key={i} className="pdf-link" style={style} href={l.url} target="_blank" rel="noopener noreferrer" title={l.url} aria-label={"外部链接 " + l.url} />
        ) : (
          <button key={i} type="button" className="pdf-link" style={style} title={`跳到第 ${l.page! + 1} 页`} aria-label={`跳到第 ${l.page! + 1} 页`}
            onClick={() => onLink(l.page!, l.top ?? null)} />
        );
      })}
      {ready && notes.flatMap((n) => n.rects.map((r, i) => {
        const style = box(r);
        return style ? <div key={n.id + ":" + i} className={"saved-annotation" + (n.rectangle ? " rectangle" : "")} data-note-id={n.id} aria-hidden="true" style={style} /> : null;
      }))}
      {ready && draftRects.map((r, i) => <div key={i} className="draft-annotation" aria-hidden="true" style={box(r)} />)}
      {ready && marks.flatMap((m) => m.rects.map((r, i) => {
        const style = box(r);
        return style ? (
          <div key={m.n + ":" + i} className={"coach-mark" + (m.current ? " current" : "")} data-mark={m.n} aria-hidden="true" style={style}>
            {i === 0 && <span className="coach-mark-n">{m.n}</span>}
          </div>
        ) : null;
      }))}
      {ready && focusRects.map((r, i) => <div key={i} className="anchor-highlight" style={box(r)} />)}
      {region && ready && (
        <div
          className="region-layer"
          onPointerDown={(e) => {
            if (!e.isPrimary || Date.now() < suppressUntil.current) { setDrag(null); return; }
            e.currentTarget.setPointerCapture?.(e.pointerId);
            const b = element.current!.getBoundingClientRect();
            setDrag({ x: e.clientX - b.left, y: e.clientY - b.top, x2: e.clientX - b.left, y2: e.clientY - b.top });
          }}
          onPointerMove={(e) => {
            if (!drag) return;
            const b = element.current!.getBoundingClientRect();
            setDrag({ ...drag, x2: e.clientX - b.left, y2: e.clientY - b.top });
          }}
          onPointerUp={(e) => {
            if (!drag || Date.now() < suppressUntil.current) { setDrag(null); return; }
            const b = element.current!.getBoundingClientRect();
            const x = Math.max(0, Math.min(e.clientX - b.left, b.width)), y = Math.max(0, Math.min(e.clientY - b.top, b.height));
            if (Math.abs(x - drag.x) > 3 && Math.abs(y - drag.y) > 3)
              onRegion(index, {
                left: b.left + Math.min(x, drag.x), right: b.left + Math.max(x, drag.x),
                top: b.top + Math.min(y, drag.y), bottom: b.top + Math.max(y, drag.y),
              }, element.current!);
            setDrag(null);
          }}
          onPointerCancel={() => setDrag(null)}
          onLostPointerCapture={() => setDrag(null)}
        >
          {drag && <div className="region-box" style={{
            left: Math.min(drag.x, drag.x2), top: Math.min(drag.y, drag.y2),
            width: Math.abs(drag.x - drag.x2), height: Math.abs(drag.y - drag.y2),
          }} />}
        </div>
      )}
    </div>
  );
}

export default memo(PdfPage);

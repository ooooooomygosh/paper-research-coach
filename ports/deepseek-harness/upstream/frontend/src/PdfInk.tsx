import { useRef, useState, type PointerEvent } from "react";
import type { Viewport } from "./PdfPage";

export type Point = [number, number];

export function InkPath({ points, viewport }: { points: Point[]; viewport: Viewport }) {
  if (!points.length) return null;
  return <svg className="pdf-ink-path" aria-hidden="true">
    <polyline points={points.map(([x, y]) => viewport.convertToViewportPoint(x, y).join(",")).join(" ")}
      fill="none" stroke="#b83131" strokeWidth={2 * viewport.scale} strokeLinecap="round" strokeLinejoin="round" />
  </svg>;
}

export function InkCapture({ viewport, onDraw, suppressUntil }: {
  viewport: Viewport;
  onDraw: (points: Point[], bounds: DOMRect) => void;
  suppressUntil: { current: number };
}) {
  const stroke = useRef<{ pointer: number; points: Point[] } | null>(null);
  const [points, setPoints] = useState<Point[]>([]);

  function point(e: PointerEvent<HTMLDivElement>, b: DOMRect): Point {
    const x = Math.min(b.width, Math.max(0, e.clientX - b.left)) / b.width * viewport.width;
    const y = Math.min(b.height, Math.max(0, e.clientY - b.top)) / b.height * viewport.height;
    const [pdfX, pdfY] = viewport.convertToPdfPoint(x, y);
    return [pdfX, pdfY];
  }

  function cancel() {
    stroke.current = null;
    setPoints([]);
  }

  return <div className="pdf-ink-capture"
    onPointerDown={(e) => {
      if (!e.isPrimary || e.button !== 0 || Date.now() < suppressUntil.current) return;
      e.currentTarget.setPointerCapture?.(e.pointerId);
      const next = [point(e, e.currentTarget.getBoundingClientRect())];
      stroke.current = { pointer: e.pointerId, points: next };
      setPoints(next);
    }}
    onPointerMove={(e) => {
      const path = stroke.current;
      if (!path || path.pointer !== e.pointerId) return;
      const next = point(e, e.currentTarget.getBoundingClientRect());
      const [x, y] = path.points[path.points.length - 1];
      if (Math.hypot(next[0] - x, next[1] - y) < 0.75) return;
      if (path.points.length >= 2047) return;
      path.points = [...path.points, next];
      setPoints(path.points);
    }}
    onPointerUp={(e) => {
      const path = stroke.current;
      if (!path || path.pointer !== e.pointerId) return;
      const bounds = e.currentTarget.getBoundingClientRect();
      const next = [...path.points, point(e, bounds)];
      cancel();
      if (Date.now() < suppressUntil.current) return;
      if (next.some(([x, y]) => Math.hypot(x - next[0][0], y - next[0][1]) >= 1)) onDraw(next, bounds);
    }}
    onPointerCancel={cancel}
    onLostPointerCapture={cancel}
  ><InkPath points={points} viewport={viewport} /></div>;
}

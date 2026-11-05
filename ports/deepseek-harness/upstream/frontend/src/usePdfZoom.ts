import { useEffect, useRef, useState, type RefObject } from "react";

export const MIN_ZOOM = 0.25;
export const MAX_ZOOM = 4;
export const boundZoom = (zoom: number) => Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, zoom));
export type ZoomFocus = { x: number; y: number; clientX: number; clientY: number };
type Point = { x: number; y: number };

/** Preview the existing canvas during a gesture; rasterize only once on release. */
export function usePdfZoom({ scroller, frame, zoom, ready, documentKey, onCommit }: {
  scroller: RefObject<HTMLDivElement | null>;
  frame: RefObject<HTMLDivElement | null>;
  zoom: number;
  ready: boolean;
  documentKey: string;
  onCommit: (zoom: number, focus: ZoomFocus) => void;
}) {
  const [preview, setPreview] = useState<number | null>(null);
  const latest = useRef({ zoom, ready, onCommit });
  latest.current = { zoom, ready, onCommit };
  const suppressSelectionUntil = useRef(0);
  useEffect(() => {
    const box = scroller.current;
    if (!box) return;
    let active: { source: string; zoom: number; next: number; origin: Point; point: Point; distance: number; element: HTMLDivElement } | null = null;
    let wheelTimer: ReturnType<typeof setTimeout>;
    const begin = (source: string, point: Point, distance = 1) => {
      if (!latest.current.ready || !frame.current) return false;
      if (active) return active.source === source;
      const element = frame.current, rect = element.getBoundingClientRect();
      active = { source, zoom: latest.current.zoom, next: latest.current.zoom, origin: { x: point.x - rect.left, y: point.y - rect.top }, point, distance, element };
      element.style.transformOrigin = `${active.origin.x}px ${active.origin.y}px`;
      box.classList.add("pdf-gesturing");
      window.getSelection()?.removeAllRanges();
      return true;
    };
    const update = (next: number, point?: Point) => {
      if (!active) return;
      active.next = boundZoom(next);
      const dx = point ? point.x - active.point.x : 0;
      const dy = point ? point.y - active.point.y : 0;
      active.element.style.transform = `translate(${dx}px, ${dy}px) scale(${active.next / active.zoom})`;
      setPreview(active.next);
      suppressSelectionUntil.current = Date.now() + 350;
    };
    const finish = (commit = true, point?: Point) => {
      clearTimeout(wheelTimer);
      if (!active) return;
      const gesture = active;
      active = null;
      gesture.element.style.transform = "";
      gesture.element.style.transformOrigin = "";
      box.classList.remove("pdf-gesturing");
      setPreview(null);
      suppressSelectionUntil.current = Date.now() + 350;
      if (commit && Math.abs(gesture.next - gesture.zoom) > 0.001) {
        latest.current.onCommit(gesture.next, {
          x: gesture.origin.x / gesture.zoom, y: gesture.origin.y / gesture.zoom,
          clientX: point?.x ?? gesture.point.x, clientY: point?.y ?? gesture.point.y,
        });
      }
    };
    const wheel = (e: WheelEvent) => {
      if (!e.ctrlKey) return; // Ordinary two-finger scrolling remains native.
      e.preventDefault();
      const point = { x: e.clientX, y: e.clientY };
      if (!begin("wheel", point) || !active) return;
      const delta = e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? box.clientHeight : 1);
      update(active.next * Math.exp(-delta * 0.008));
      clearTimeout(wheelTimer);
      wheelTimer = setTimeout(() => finish(), 130);
    };
    const touchPoint = (touches: TouchList) => ({
      x: (touches[0].clientX + touches[1].clientX) / 2,
      y: (touches[0].clientY + touches[1].clientY) / 2,
    });
    const distance = (touches: TouchList) => Math.hypot(touches[0].clientX - touches[1].clientX, touches[0].clientY - touches[1].clientY);
    let lastTouch: Point | undefined;
    const touchStart = (e: TouchEvent) => {
      if (e.touches.length < 2) return;
      e.preventDefault();
      lastTouch = touchPoint(e.touches);
      begin("touch", lastTouch, Math.max(1, distance(e.touches)));
    };
    const touchMove = (e: TouchEvent) => {
      if (e.touches.length < 2) return;
      e.preventDefault();
      if (!active) touchStart(e);
      if (active?.source !== "touch") return;
      lastTouch = touchPoint(e.touches);
      update(active.zoom * distance(e.touches) / active.distance, lastTouch);
    };
    const touchEnd = (e: TouchEvent) => {
      if (active?.source === "touch" && e.touches.length < 2) finish(true, lastTouch);
    };
    // Safari trackpads use gesture events; Chromium/Firefox use ctrl+wheel.
    type Gesture = Event & { scale: number; clientX: number; clientY: number };
    const safariStart = (event: Event) => {
      event.preventDefault();
      const e = event as Gesture, rect = box.getBoundingClientRect();
      begin("safari", { x: e.clientX || rect.left + rect.width / 2, y: e.clientY || rect.top + rect.height / 2 });
    };
    const safariChange = (event: Event) => {
      event.preventDefault();
      if (active?.source === "safari") update(active.zoom * (event as Gesture).scale);
    };
    const safariEnd = (event: Event) => { event.preventDefault(); if (active?.source === "safari") finish(); };
    const cancel = () => finish(false);
    box.addEventListener("wheel", wheel, { passive: false });
    box.addEventListener("touchstart", touchStart, { passive: false });
    box.addEventListener("touchmove", touchMove, { passive: false });
    box.addEventListener("touchend", touchEnd);
    box.addEventListener("touchcancel", cancel);
    box.addEventListener("gesturestart", safariStart, { passive: false });
    box.addEventListener("gesturechange", safariChange, { passive: false });
    box.addEventListener("gestureend", safariEnd, { passive: false });
    return () => {
      cancel();
      box.removeEventListener("wheel", wheel);
      box.removeEventListener("touchstart", touchStart);
      box.removeEventListener("touchmove", touchMove);
      box.removeEventListener("touchend", touchEnd);
      box.removeEventListener("touchcancel", cancel);
      box.removeEventListener("gesturestart", safariStart);
      box.removeEventListener("gesturechange", safariChange);
      box.removeEventListener("gestureend", safariEnd);
    };
  }, [documentKey]);
  return { displayZoom: preview ?? zoom, suppressSelectionUntil };
}

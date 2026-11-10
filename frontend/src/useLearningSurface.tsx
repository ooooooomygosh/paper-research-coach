import { useEffect, useRef, useState, type RefObject } from "react";

export function splitWidth(width: number, ratio: number) {
  return Math.max(440, Math.min(width - 624, width * ratio));
}

/** Presentation only: consumers keep their renderer and iframe mounted. */
export function useLearningSurface(root: RefObject<HTMLElement | null>, initial = false) {
  const [expanded, setExpanded] = useState(initial), [compare, setCompare] = useState(false);
  const [paper, setPaper] = useState(false), [ratio, setRatio] = useState(.44);
  const [bounds, setBounds] = useState({left:12, top:12, width:window.innerWidth-24, height:window.innerHeight-24});
  const [systemFull,setSystemFull] = useState(false);
  useEffect(()=>{const changed=()=>setSystemFull(document.fullscreenElement===root.current);document.addEventListener("fullscreenchange",changed);return()=>document.removeEventListener("fullscreenchange",changed);},[root]);
  const trigger = useRef<HTMLElement | null>(null);
  useEffect(() => { trigger.current = document.activeElement as HTMLElement; return () => trigger.current?.focus?.({preventScroll:true}); }, []);
  const wasExpanded = useRef(false);
  useEffect(() => {
    if (expanded) {
      if (!root.current?.contains(document.activeElement)) trigger.current = document.activeElement as HTMLElement;
      root.current?.focus({preventScroll:true});
    } else if (wasExpanded.current) trigger.current?.focus?.({preventScroll:true});
    wasExpanded.current = expanded;
  },[expanded,root]);
  useEffect(() => {
    const host = document.querySelector("main");
    const measure = () => {
      const r = host?.getBoundingClientRect(), header = host?.querySelector(".topbar")?.getBoundingClientRect();
      const left = (r?.width ? r.left : 0) + 12, top = Math.max(r?.top || 0, header?.bottom || 0) + 12;
      const next = {left, top, width:Math.max(1,(r?.width || window.innerWidth)-24), height:Math.max(100,window.innerHeight-top-12)};
      setBounds(old => Object.keys(next).every(key => old[key as keyof typeof old] === next[key as keyof typeof next]) ? old : next);
    };
    let frame = 0;
    const schedule = () => { if (!frame) frame = requestAnimationFrame(() => { frame = 0; measure(); }); };
    measure(); const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(schedule);
    if (host) observer?.observe(host);
    window.addEventListener("resize", schedule);
    return () => { cancelAnimationFrame(frame); observer?.disconnect(); window.removeEventListener("resize", schedule); };
  }, []);
  const wide = bounds.width >= 1120, leftWidth = splitWidth(bounds.width, ratio);
  useEffect(() => {
    if (!compare) return;
    const html = document.documentElement;
    html.setAttribute("data-learning-compare", wide ? "wide" : paper ? "paper" : "lesson");
    for (const [k,v] of Object.entries({left:bounds.left, top:bounds.top, height:bounds.height, width:wide ? leftWidth : bounds.width})) html.style.setProperty("--learning-paper-"+k,v+"px");
    return () => { html.removeAttribute("data-learning-compare"); for (const k of ["left","top","height","width"]) html.style.removeProperty("--learning-paper-"+k); };
  }, [compare, wide, paper, bounds, leftWidth]);
  const expand = () => { setCompare(false); setExpanded(!expanded); };
  const fullscreen = async () => { try { if(document.fullscreenElement) await document.exitFullscreen(); else await root.current?.requestFullscreen(); } catch { setExpanded(true); } };
  const escape = () => { if(document.fullscreenElement) { void document.exitFullscreen(); return true; } if(compare) { setCompare(false); return true; } if(expanded) { setExpanded(false); return true; } return false; };
  const style = expanded && !systemFull ? {position:"fixed" as const, left:compare && wide ? bounds.left+leftWidth+24 : bounds.left, top:bounds.top,
    width:compare && wide ? bounds.width-leftWidth-24 : bounds.width, height:bounds.height, right:"auto", bottom:"auto", margin:0, maxWidth:"none"} : {};
  return {systemFull, expanded, setExpanded, compare, setCompare, paper, setPaper, ratio, setRatio, bounds, wide, leftWidth, expand, fullscreen, escape, style};
}
export function LearningCompareControls({surface:s}: {surface:ReturnType<typeof useLearningSurface>}) {
  if (!s.compare || s.systemFull) return null;
  return s.wide ? <div role="separator" aria-label="调整论文与讲解宽度" aria-orientation="vertical" aria-valuemin={440} aria-valuemax={Math.floor(s.bounds.width-624)} aria-valuenow={Math.round(s.leftWidth)} tabIndex={0}
    style={{position:"fixed",left:s.bounds.left+s.leftWidth,top:s.bounds.top,width:24,height:s.bounds.height,cursor:"col-resize",zIndex:90,touchAction:"none"}}
    onKeyDown={e=>{if(e.key==="ArrowLeft"||e.key==="ArrowRight"){e.preventDefault();s.setRatio((s.leftWidth+(e.key==="ArrowLeft"?-24:24))/s.bounds.width);}}}
    onPointerDown={e=>{e.currentTarget.setPointerCapture?.(e.pointerId);}}
    onPointerMove={e=>{if(e.buttons===1)s.setRatio(Math.max(440,Math.min(s.bounds.width-624,e.clientX-s.bounds.left))/s.bounds.width);}}><span style={{display:"block",height:"100%",width:2,background:"var(--line, #888)",margin:"auto"}} /></div>
    : <div className="learning-narrow-tabs" role="group" aria-label="论文与讲解切换"><button aria-pressed={s.paper} onClick={()=>s.setPaper(true)}>论文</button><button aria-pressed={!s.paper} onClick={()=>s.setPaper(false)}>讲解</button></div>;
}

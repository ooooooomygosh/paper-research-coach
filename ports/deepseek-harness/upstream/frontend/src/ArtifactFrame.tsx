import { useLearningSurface, LearningCompareControls } from "./useLearningSurface";
import React, { useEffect, useRef, useState } from "react";
import { Maximize2, Minimize2 } from "./glyphs";
import { workspaceApi, workspaceUrl, versionQuery } from "./workspace-api";

export function artifactMessage(event: MessageEvent, source: Window | null, kind: string, id: string) {
  const data = event.data;
  if (!source || event.source !== source || !data || data.channel !== "prc-workspace-v1" || data.scope?.id !== id || data.scope?.type !== kind) return null;
  if (data.kind === "question" && typeof data.text === "string" && data.text.length <= 16000) return { ...data, action: data.kind };
  if (data.kind === 'locate') return { ...data, action: 'locate' };
  if (data.kind === "storage" && typeof data.key === "string" && data.key.length <= 500 && (data.value === null || typeof data.value === "string" && data.value.length <= 500000)) return { ...data, action: data.kind };
  return null;
}

export default function ArtifactFrame({ kind, id, version, title, onQuestion, report, onLocate }: {
  kind: "studio" | "kb"; id: string; version: string; title: string;
  onQuestion: (text: string, context?: { unit_id?: string; method_id?: string }) => void; report: (message: string) => void;
  onLocate?: () => boolean | void;
}) {
  const frame = useRef<HTMLIFrameElement>(null), box = useRef<HTMLDivElement>(null);
  const [wide, setWide] = useState(false);
  const surface = useLearningSurface(box);
  const {expanded, setExpanded, setCompare} = surface;
  function continueQuestion(text: string, context: Record<string, string>) {
    setCompare(false);
    setExpanded(false);
    const deliver = () => onQuestion(text, context);
    if (document.fullscreenElement === box.current && document.exitFullscreen) {
      void document.exitFullscreen().then(deliver, deliver);
    } else deliver();
  }
  const latest = useRef({ continueQuestion, report, onLocate });
  latest.current = { continueQuestion, report, onLocate };
  const queue = useRef(Promise.resolve());
  useEffect(() => {
    function receive(event: MessageEvent) {
      const data = artifactMessage(event, frame.current?.contentWindow || null, kind, id);
      if (!data) return;
      if (data.action === "question") {
        const context = Object.fromEntries(["unit_id", "method_id"].filter(key => typeof data[key] === "string" && /^[a-zA-Z0-9_-]{1,80}$/.test(data[key])).map(key => [key, data[key]]));
        latest.current.continueQuestion(data.text, context);
      } else if (data.action === 'locate') {
        // The anchor belongs to the selected publication, never to message data.
        latest.current.onLocate?.();
      } else {
        // Serialize writes: rapid per-character note changes must keep their order.
        queue.current = queue.current.then(() => workspaceApi(`/storage/${kind}/${id}`, { key: data.key, value: data.value }, "PUT"))
          .catch(error => latest.current.report("学习记录未保存：" + error.message));
      }
    }
    window.addEventListener("message", receive);
    return () => window.removeEventListener("message", receive);
  }, [id, kind]);
  useEffect(() => {
    function changed() { setWide(document.fullscreenElement === box.current); }
    document.addEventListener("fullscreenchange", changed);
    return () => document.removeEventListener("fullscreenchange", changed);
  }, []);
  async function fullscreen() {
    await surface.fullscreen();
  }
  function toggleCompare() {
    if (surface.compare) { setCompare(false); return; }
    if (onLocate) {
      if (onLocate() === false) return;
    } else if (!document.querySelector(".workspace-original,.reading-layout")) {
      report("请先显示当前论文，再开启论文对照。");
      return;
    }
    setExpanded(true);
    surface.setPaper(false);
    setCompare(true);
  }
  return <div className={"artifact-frame" + (expanded ? " learning-surface-expanded" : "")} ref={box} tabIndex={-1} style={wide ? undefined : surface.style} data-paper-visible={surface.compare && !surface.wide && surface.paper ? "true" : undefined} onKeyDown={e => { if (e.key === "Escape" && surface.escape()) e.stopPropagation(); }}>
    <LearningCompareControls surface={surface} />
    <div className="artifact-toolbar"><span>{title}</span><button onClick={surface.expand}>{expanded ? "返回工作台" : "展开讲解"}</button><button aria-pressed={surface.compare} onClick={toggleCompare}>与论文对照</button><button onClick={() => void fullscreen()} aria-label={wide ? "退出页面全屏" : "学习页面全屏"}>
      {wide ? <Minimize2 size={15} /> : <Maximize2 size={15} />} 全屏</button></div>
    <iframe key={id + version} ref={frame} title={title} src={workspaceUrl(`/view/${kind}/${id}`) + versionQuery(version)}
      sandbox="allow-scripts allow-forms allow-downloads allow-modals" allow="fullscreen; clipboard-write" />
  </div>;
}

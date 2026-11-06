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
  onLocate?: () => void;
}) {
  const frame = useRef<HTMLIFrameElement>(null), box = useRef<HTMLDivElement>(null);
  const [wide, setWide] = useState(false);
  const latest = useRef({ onQuestion, report, onLocate });
  latest.current = { onQuestion, report, onLocate };
  const queue = useRef(Promise.resolve());
  useEffect(() => {
    function receive(event: MessageEvent) {
      const data = artifactMessage(event, frame.current?.contentWindow || null, kind, id);
      if (!data) return;
      if (data.action === "question") {
        const context = Object.fromEntries(["unit_id", "method_id"].filter(key => typeof data[key] === "string" && /^[a-zA-Z0-9_-]{1,80}$/.test(data[key])).map(key => [key, data[key]]));
        latest.current.onQuestion(data.text, context);
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
    try { if (document.fullscreenElement) await document.exitFullscreen(); else await box.current?.requestFullscreen(); }
    catch { latest.current.report("当前窗口不支持全屏，可收起左侧论文栏扩大页面。"); }
  }
  return <div className="artifact-frame" ref={box}>
    <div className="artifact-toolbar"><span>{title}</span><button onClick={() => void fullscreen()} aria-label={wide ? "退出页面全屏" : "学习页面全屏"}>
      {wide ? <Minimize2 size={15} /> : <Maximize2 size={15} />} 全屏</button></div>
    <iframe key={id + version} ref={frame} title={title} src={workspaceUrl(`/view/${kind}/${id}`) + versionQuery(version)}
      sandbox="allow-scripts allow-forms allow-downloads allow-modals" allow="fullscreen; clipboard-write" />
  </div>;
}

import React, { useEffect, useState, useRef } from "react";
import { X } from "lucide-react";
import { api, id, anchorQuote, type Row } from "./api";
import { hasTranslation } from "./TranslationLibrary";

export type PdfView = "original" | "mono" | "dual";

export function TranslationTools({
  paper,
  job,
  readableJob,
  reload,
  view,
  setView,
  open,
}: {
  paper: Row;
  job: any;
  readableJob?: any;
  reload: () => void;
  view: PdfView;
  setView: (v: PdfView) => void;
  open: boolean;
}) {
  const [profile, setProfile] = useState<any>(null),
    [models, setModels] = useState<any[]>([]);
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [saving, setSaving] = useState(false);
  useEffect(() => {
    if (!open) return;
    let disposed = false;
    Promise.all([api("translation/settings"), api("coach/status")])
      .then(([p, s]) => {
        if (!disposed) {
          setProfile(p);
          setModels(s.models || []);
        }
      })
      .catch(() => {
        if (!disposed) setError("翻译设置暂不可用，请重新打开工具菜单。");
      });
    return () => {
      disposed = true;
    };
  }, [open]);
  async function save(next: any) {
    const previous = profile;
    setSaving(true);
    setProfile(next);
    try {
      await api("translation/settings", {
        model: next.model,
        effort: next.effort,
        lang_in: next.lang_in,
        lang_out: next.lang_out,
        paper_concurrency: next.paper_concurrency ?? 2,
        request_concurrency: next.request_concurrency ?? 4,
      });
      setError("");
    } catch (e) {
      setProfile(previous);
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }
  async function action(kind: "start" | "stop" | "retry") {
    setBusy(true);
    setError("");
    try {
      if (kind === "start") {
        const key =
          "prc-translation-request-" + paper.id + ":" + paper.source_version;
        const operation = localStorage.getItem(key) || id();
        localStorage.setItem(key, operation);
        await api("translation/" + paper.id + "/jobs", {
          operation_id: operation,
          source_version: paper.source_version,
        });
        localStorage.removeItem(key);
      } else await api("translation/jobs/" + job.id + "/" + kind, {});
      reload();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  const selected = models.find((m) => m.model === profile?.model);
  const running = job && ["queued", "running"].includes(job.state);
  const readJob = hasTranslation(job) ? job : readableJob;
  const readable = hasTranslation(readJob);
  return (
    <section className="translation-tools">
      <h3>整篇双语翻译</h3>
      <p>翻译独立运行，沿用 Codex 登录。完成后，选句即可查看对应中文。</p>
      {profile && (
        <>
          <label>
            翻译模型
            <select
              aria-label="翻译模型"
              disabled={saving}
              value={profile.model}
              onChange={(e) => {
                const model = models.find((m) => m.model === e.target.value);
                const effort = model?.supportedReasoningEfforts?.some(
                  (r: any) => r.reasoningEffort === "low",
                )
                  ? "low"
                  : model?.defaultReasoningEffort || "low";
                void save({ ...profile, model: e.target.value, effort });
              }}
            >
              {!models.some((m) => m.model === profile.model) && (
                <option value={profile.model}>
                  {profile.model} · 当前不可用
                </option>
              )}
              {models.map((m) => (
                <option key={m.model} value={m.model}>
                  {m.displayName || m.model}
                </option>
              ))}
            </select>
          </label>
          <label>
            翻译思考深度
            <select
              aria-label="翻译思考深度"
              disabled={saving}
              value={profile.effort}
              onChange={(e) =>
                void save({ ...profile, effort: e.target.value })
              }
            >
              {(
                selected?.supportedReasoningEfforts || [
                  { reasoningEffort: "low" },
                ]
              ).map((r: any) => (
                <option key={r.reasoningEffort} value={r.reasoningEffort}>
                  {r.reasoningEffort}
                </option>
              ))}
            </select>
          </label>
          {!profile.component?.ready && (
            <p role="status">请先安装可选翻译组件，再生成整篇译文。</p>
          )}
        </>
      )}
      {job && (
        <div className="translation-job" role="status">
          <p>
            {
              (
                {
                  queued: "等待翻译",
                  running: "翻译中",
                  completed: "翻译完成",
                  failed: "翻译未完成",
                  cancelled: "已停止",
                  interrupted: "可以继续翻译",
                } as Record<string, string>
              )[job.state]
            }
          </p>
          {running && job.stage && <small>{job.stage}</small>}
          {running && (
            <progress
              aria-label="翻译进度"
              max={100}
              value={job.progress || 0}
            />
          )}
          {job.message && <p>{job.message}</p>}
          <small>此任务使用 {job.model}</small>
        </div>
      )}
      {running ? (
        <button disabled={busy} onClick={() => void action("stop")}>
          停止翻译
        </button>
      ) : job && ["failed", "cancelled", "interrupted"].includes(job.state) ? (
        <button disabled={busy} onClick={() => void action("retry")}>
          继续翻译
        </button>
      ) : (
        <button
          className="primary"
          disabled={
            busy ||
            saving ||
            !profile?.component?.ready ||
            !selected ||
            !paper.source_version
          }
          onClick={() => void action("start")}
        >
          {job?.state === "completed" ? "重新生成整篇译文" : "生成整篇双语 PDF"}
        </button>
      )}
      {readable && (
        <>
          <label>
            阅读视图
            <select
              aria-label="PDF 阅读视图"
              value={view}
              onChange={(e) => setView(e.target.value as PdfView)}
            >
              <option value="original">原文</option>
              <option value="mono">中文译文</option>
              <option value="dual">中英对照</option>
            </select>
          </label>
          <div className="translation-downloads">
            <a
              href={`/api/translation/jobs/${readJob.id}/pdf/dual`}
              download={`${paper.title}.双语.pdf`}
            >
              下载双语 PDF
            </a>
            <a
              href={`/api/translation/jobs/${readJob.id}/pdf/mono`}
              download={`${paper.title}.中文.pdf`}
            >
              下载中文 PDF
            </a>
          </div>
        </>
      )}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}

export function TranslationPopover({
  selection,
  job,
  onClose,
  onDiscuss,
  onSource,
  onMark,
  onNote,
}: {
  selection: { anchor: any; view: PdfView; x: number; y: number };
  job: any;
  onClose: () => void;
  onDiscuss: (a: any) => void;
  onSource: (a: any) => void;
  onMark?: (a: any) => Promise<void>;
  onNote?: (a: any) => void;
}) {
  const [result, setResult] = useState<any>(null),
    [error, setError] = useState(""),
    [saving, setSaving] = useState(false),
    [saved, setSaved] = useState(false);
  useEffect(() => {
    let disposed = false;
    setResult(null);
    setError("");
    setSaved(false);
    if (!hasTranslation(job) || !anchorQuote(selection.anchor)) return;
    const rendition = selection.anchor.rendition;
    api(`translation/jobs/${job.id}/selection`, {
      anchor: rendition ? { ...selection.anchor, page_index: rendition.page_index, page_label: rendition.page_label, quote: rendition.quote, rects: rendition.rects, rendition: null } : selection.anchor,
      view: selection.view,
    })
      .then((r) => {
        if (!disposed) {
          const source = r.source_anchor && (rendition ? { ...r.source_anchor, rendition } : r.source_anchor);
          setResult({ ...r, source_anchor: source });
          if (source) onSource(source);
        }
      })
      .catch(() => {
        if (!disposed) setError("对应译文暂不可用。");
      });
    return () => {
      disposed = true;
    };
  }, [job?.id, job?.state, job?.pdf_ready, selection]);
  useEffect(() => {
    function escape(e: KeyboardEvent) {
      if (e.key === "Escape" && !document.querySelector("dialog[open]")) {
        e.preventDefault();
        e.stopImmediatePropagation();
        onClose();
      }
    }
    document.addEventListener("keydown", escape, true);
    return () => document.removeEventListener("keydown", escape, true);
  }, [onClose]);
  const source = result?.source_anchor || selection.anchor;
  const discussionSource = result?.source_anchor || (selection.view === "original" ? selection.anchor : null);
  const markAnchor = useRef<any>(null);
  return (
    <div
      className="translation-popover"
      role="dialog"
      aria-label={!anchorQuote(selection.anchor) ? "区域批注" : hasTranslation(job) ? "对应中文" : "原文选区"}
      style={{
        left: Math.max(12, Math.min(selection.x, window.innerWidth - 360)),
        top: Math.max(12, Math.min(selection.y, window.innerHeight - 300)),
      }}
    >
      <div className="translation-popover-heading">
        <span>{!anchorQuote(selection.anchor) ? "区域批注" : !hasTranslation(job) ? "原文选区" : result?.level === "paragraph" ? "对应段落" : "对应中文"}</span>
        <button aria-label="关闭译文" onClick={onClose}>
          <X size={15} />
        </button>
      </div>
      <p>
        {error ||
          result?.text ||
          result?.message ||
          (!anchorQuote(selection.anchor) ? "已框选这处区域，可保存标记或记下你的想法。" : hasTranslation(job)
            ? "正在查找对应译文…"
            : anchorQuote(selection.anchor) || "已选择原文位置。")}
      </p>
      {!hasTranslation(job) && !!anchorQuote(selection.anchor) && <p className="selection-help">可以直接讨论这句话，不需要先翻译整篇论文。</p>}
      <div className="selection-actions">
      {onMark && <button disabled={saving || saved} onClick={async () => {
        setSaving(true);
        try { markAnchor.current ||= source; await onMark(markAnchor.current); setSaved(true); } catch { setError("标记未保存，请重试。"); } finally { setSaving(false); }
      }}>{saved ? "已保留在 PDF" : saving ? "正在保存…" : "保留标记"}</button>}
      {onNote && <button onClick={() => { onNote(source); onClose(); }}>记笔记</button>}
      <button
        disabled={!discussionSource}
        title={!discussionSource ? "这处译文尚未对应原文，可先保存批注" : undefined}
        onClick={() => {
          onDiscuss(discussionSource);
          onClose();
        }}
      >
        讨论这处
      </button>
      </div>
    </div>
  );
}

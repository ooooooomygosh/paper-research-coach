import { useEffect, useRef, useState } from "react";
import {
  Plus,
  Check,
  MessageCircle,
  MapPin,
  History,
  Link2,
} from "lucide-react";
import { api, put, id, location, ApiError, type Row } from "./api";
export default function Notes({
  paper,
  notes,
  anchor,
  onLocate,
  refresh,
  report,
}: {
  paper: Row;
  notes: Row[];
  anchor: any;
  onLocate: (a: any) => void;
  refresh: () => void;
  report: (s: string) => void;
}) {
  const key = "prc-draft-" + paper.id;
  const jobKey = key + "-operation";
  function cachedJob() {
    try {
      return JSON.parse(localStorage.getItem(jobKey) || "null");
    } catch {
      return null;
    }
  }
  function initial() {
    try {
      return (
        JSON.parse(localStorage.getItem(key) || "null") || {
          id: id(),
          paper_id: paper.id,
          content: "",
          author: "user",
          provenance: "USER",
          revision: 0,
          anchor: null,
        }
      );
    } catch {
      return {
        id: id(),
        paper_id: paper.id,
        content: "",
        author: "user",
        provenance: "USER",
        revision: 0,
        anchor: null,
      };
    }
  }
  const [draft, setDraft] = useState<any>(initial),
    [status, setStatus] = useState(() =>
      draft.content ? "正在恢复未完成的保存…" : "",
    ),
    [history, setHistory] = useState<any[] | null>(null);
  const latestNotes = useRef(notes);
  latestNotes.current = notes;
  const current = useRef(draft),
    busy = useRef(false),
    timer = useRef<any>(null),
    retry = useRef<any>(cachedJob()),
    attempts = useRef(0),
    alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    const reconnect = () => {
      attempts.current = 0;
      void save();
    };
    window.addEventListener("online", reconnect);
    timer.current = setTimeout(() => void save(), 100);
    return () => {
      window.removeEventListener("online", reconnect);
      alive.current = false;
      clearTimeout(timer.current);
      void save();
    };
  }, []);
  useEffect(() => {
    const n = notes.find((n) => n.id === current.current.id);
    if (
      !busy.current &&
      !retry.current &&
      n &&
      n.revision > current.current.revision &&
      n.content === current.current.content &&
      JSON.stringify(n.anchor) === JSON.stringify(current.current.anchor)
    ) {
      current.current = n;
      setDraft(n);
      localStorage.setItem(key, JSON.stringify(n));
      setStatus(n.discussed ? "已保存 · 已讨论" : "已保存 · 等待讨论");
    }
  }, [notes]);
  useEffect(() => {
    if (anchor) {
      const next = { ...current.current, anchor };
      update(next);
    }
  }, [anchor]);
  function update(next: any) {
    if (
      next.content !== current.current.content ||
      JSON.stringify(next.anchor) !== JSON.stringify(current.current.anchor)
    )
      next = { ...next, discussed: false };
    current.current = next;
    setDraft(next);
    localStorage.setItem(key, JSON.stringify(next));
    setStatus("正在保存…");
    clearTimeout(timer.current);
    timer.current = setTimeout(() => void save(), 450);
  }
  async function save() {
    if (busy.current || !current.current.content.trim()) return;
    const same = latestNotes.current.find(
      (n) =>
        n.id === current.current.id &&
        n.revision === current.current.revision &&
        n.content === current.current.content &&
        JSON.stringify(n.anchor) === JSON.stringify(current.current.anchor),
    );
    if (same && !retry.current) {
      if (alive.current)
        setStatus(same.discussed ? "已保存 · 已讨论" : "已保存 · 等待讨论");
      return;
    }
    busy.current = true;
    const value = { ...current.current };
    const job = retry.current || { value, op: id() };
    // Persist the exact transaction before sending it, including unknown-outcome retries.
    try {
      localStorage.setItem(jobKey, JSON.stringify(job));
      const saved = await put("note", job.value, job.op);
      // A newer mount owns the shared draft after this component leaves.
      if (!alive.current || current.current.id !== job.value.id) return;
      retry.current = null;
      attempts.current = 0;
      const changed =
        current.current.content !== job.value.content ||
        JSON.stringify(current.current.anchor) !==
          JSON.stringify(job.value.anchor);
      const next = {
        ...saved,
        ...current.current,
        revision: saved.revision,
        discussed: changed ? false : saved.discussed,
      };
      latestNotes.current = [
        ...latestNotes.current.filter((n) => n.id !== saved.id),
        saved,
      ];
      current.current = next;
      localStorage.setItem(key, JSON.stringify(next));
      if (cachedJob()?.op === job.op) localStorage.removeItem(jobKey);
      if (alive.current) {
        setDraft(next);
        setStatus(next.discussed ? "已保存 · 已讨论" : "已保存 · 等待讨论");
        refresh();
      }
      if (alive.current && changed)
        timer.current = setTimeout(() => void save(), 50);
    } catch (e) {
      retry.current = job;
      if (alive.current) {
        setStatus("未写入笔记库 · 草稿仍在此浏览器");
        if (attempts.current === 0) report(String(e));
        const permanent = e instanceof ApiError && e.status < 500;
        if (!permanent) {
          clearTimeout(timer.current);
          timer.current = setTimeout(
            () => void save(),
            Math.min(30000, 1000 * 2 ** Math.min(attempts.current++, 5)),
          );
        }
      }
    } finally {
      busy.current = false;
    }
  }
  async function fresh() {
    if (busy.current) return;
    const snapshot = current.current;
    await save();
    if (retry.current || busy.current) return;
    if (
      snapshot.content !== current.current.content ||
      JSON.stringify(snapshot.anchor) !== JSON.stringify(current.current.anchor)
    ) {
      setStatus("新输入正在保存，请保存后再切换想法");
      return;
    }
    const next = {
      id: id(),
      paper_id: paper.id,
      content: "",
      author: "user",
      provenance: "USER",
      revision: 0,
      anchor: null,
    };
    current.current = next;
    setDraft(next);
    setStatus("");
    localStorage.setItem(key, JSON.stringify(next));
  }
  async function edit(n: Row) {
    if (busy.current) return;
    const snapshot = current.current;
    await save();
    if (retry.current || busy.current) return;
    if (
      snapshot.content !== current.current.content ||
      JSON.stringify(snapshot.anchor) !== JSON.stringify(current.current.anchor)
    ) {
      setStatus("新输入正在保存，请保存后再切换想法");
      return;
    }
    current.current = n;
    setDraft(n);
    localStorage.setItem(key, JSON.stringify(n));
    setStatus("编辑会保留原版本");
  }
  async function recover() {
    if (busy.current) {
      setStatus("正在完成上次保存，请稍后再保留独立笔记");
      return;
    }
    const next = {
      ...current.current,
      id: id(),
      revision: 0,
      links: [...(current.current.links || []), current.current.id],
    };
    retry.current = null;
    localStorage.removeItem(jobKey);
    current.current = next;
    update(next);
  }
  const pending = notes.filter((n) => !n.discussed).length;
  return (
    <aside className="notes-panel">
      <div className="panel-title">
        <div>
          <span className="eyebrow">留下自己的声音</span>
          <h2>随手记下</h2>
        </div>
        <MessageCircle size={20} />
      </div>
      <p className="muted small">
        问题、反驳、不确定的直觉，都可以从这里开始。
      </p>
      <div className="composer">
        <textarea
          aria-label="记录想法"
          placeholder="刚才读到这里，我在想…"
          value={draft.content}
          onChange={(e) =>
            update({ ...current.current, content: e.target.value })
          }
        />
        <div className="anchor-chip">
          <MapPin size={13} />
          {location(draft.anchor)}
          {draft.anchor && (
            <button
              aria-label="移除位置"
              onClick={() => update({ ...current.current, anchor: null })}
            >
              ×
            </button>
          )}
        </div>
        {draft.anchor?.quote && <blockquote>{draft.anchor.quote}</blockquote>}
        <div className="save-row">
          <span>
            <Check size={12} />
            {status || "输入后自动保存原话"}
          </span>
          <button title="开始新的想法" onClick={fresh}>
            <Plus size={15} />
            新想法
          </button>
        </div>
        {retry.current && (
          <div className="button-row">
            <button onClick={() => void save()}>重试保存</button>
            <button onClick={recover}>保留为独立笔记</button>
          </div>
        )}
      </div>
      <div className="notes-heading">
        <h3>
          阅读笔记 <span>{notes.length}</span>
        </h3>
        <span>{pending} 条待讨论</span>
      </div>
      <p className="muted small">
        回到 Codex、Claude Code 或 Pi 说“继续”，一起讨论新想法。
      </p>
      <div className="note-list">
        {[...notes].reverse().map((n) => (
          <article
            className={
              "note-card " + (n.author === "assistant" ? "ai-note" : "")
            }
            key={n.id}
          >
            <div className="note-meta">
              <b>
                {n.author === "user"
                  ? "我的原话"
                  : n.author === "assistant"
                    ? "AI 评论"
                    : "Zotero 笔记"}
              </b>
              <span className={n.discussed ? "discussed" : "pending"}>
                {n.discussed ? "已讨论" : "已保存"}
              </span>
            </div>
            {n.anchor && (
              <button
                className="text-button note-location"
                onClick={() => onLocate(n.anchor)}
              >
                <MapPin size={12} />
                {location(n.anchor)}
              </button>
            )}
            <p className="preserve">{n.content}</p>
            {n.links?.length > 0 && (
              <span className="small muted">
                <Link2 size={12} /> 关联 {n.links.length} 条笔记
              </span>
            )}
            <div className="note-actions">
              {!n.read_only && n.author !== "assistant" && (
                <button className="text-button" onClick={() => edit(n)}>
                  修改
                </button>
              )}
              <button
                className="text-button"
                onClick={async () => {
                  try {
                    setHistory(await api("history/" + n.id));
                  } catch (e) {
                    report(String(e));
                  }
                }}
              >
                <History size={12} />
                修订记录
              </button>
            </div>
          </article>
        ))}
        {!notes.length && (
          <div className="empty small">
            第一条思考不需要完整。
            <br />
            先留下一个具体的问题。
          </div>
        )}
      </div>
      {history && (
        <div className="modal-backdrop" onClick={() => setHistory(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>每次修订都保留</h2>
            {history.map((h) => (
              <article className="note-card" key={h.seq}>
                <b>
                  版本 {h.revision} · {new Date(h.created_at).toLocaleString()}
                </b>
                <p className="preserve">{h.data.content}</p>
              </article>
            ))}
            <button onClick={() => setHistory(null)}>关闭</button>
          </div>
        </div>
      )}
    </aside>
  );
}

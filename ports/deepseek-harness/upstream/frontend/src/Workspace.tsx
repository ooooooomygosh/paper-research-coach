import React, { useCallback, useEffect, useRef, useState } from "react";
import { BookOpen, Layers3, Plus, Sparkles, Square } from "lucide-react";
import { activeJob, jobLabel, RecordData, workspaceApi } from "./workspace-api";
import LearningWorkspace from "./LearningWorkspace";
import InteractiveStudio from "./InteractiveStudio";
import "./workspace.css";

export type WorkspaceProps = { mode: string; paper?: RecordData; page: number; quote?: string; report: (message: string) => void };
export function JobStatus({ job, onCancel }: { job?: RecordData; onCancel: () => void }) {
  if (!job) return null;
  const running = ["running", "queued"].includes(job.state);
  return <div className={"workspace-job " + job.state} role="status">
    <div><strong>{jobLabel[job.state] || job.state} · {job.stage}</strong>
      {!!job.total && <span> {job.done} / {job.total}</span>}
      {job.message && <p>{job.message}</p>}
      {running && <progress max={job.total || 1} value={job.total ? job.done : undefined} />}
    </div>
    {running && <button onClick={onCancel}><Square size={13} />停止</button>}
  </div>;
}

export default function Workspace({ mode, paper, page, quote, report }: WorkspaceProps) {
  const [state, setState] = useState<RecordData>({ studios: [], kbs: [], jobs: [] });
  const [kb, setKb] = useState(() => localStorage.getItem("prc-workspace-kb") || ""), [studio, setStudio] = useState(() => localStorage.getItem("prc-workspace-studio") || "");
  const [methodRequest, setMethodRequest] = useState<RecordData | null>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [newKb, setNewKb] = useState(false), [title, setTitle] = useState("");
  const [depth, setDepth] = useState("quick");
  const mounted = useRef(true);
  const reload = useCallback(async () => {
    const next = await workspaceApi();
    if (mounted.current) { setState(next); setError(""); }
    return next;
  }, []);
  useEffect(() => {
    mounted.current = true;
    void reload().catch(error => setError(error.message));
    const timer = window.setInterval(() => { void reload().catch(error => setError(error.message)); }, 1800);
    return () => { mounted.current = false; clearInterval(timer); };
  }, [reload]);
  const isKb = mode === "knowledge", rows = isKb ? state.kbs : state.studios;
  const selected = isKb ? kb : studio;
  useEffect(() => { if (selected) localStorage.setItem(isKb ? "prc-workspace-kb" : "prc-workspace-studio", selected); }, [isKb, selected]);
  useEffect(() => {
    if (!selected && rows.length) (isKb ? setKb : setStudio)(rows[0].id);
  }, [isKb, rows, selected]);
  async function create() {
    setBusy(true);
    try {
      const row = await workspaceApi(isKb ? "/kbs" : "/studios", isKb ? { title, depth } : { context: paper ? { paper_id: paper.id, page_index: page, quote } : {} });
      (isKb ? setKb : setStudio)(row.id); setNewKb(false); setTitle(""); await reload();
    } catch (error) { report(String(error)); }
    finally { setBusy(false); }
  }
  const props = { jobs: state.jobs as RecordData[], reload, report };
  return <div className="workspace-shell">
    <header className="workspace-heading">
      <div><span className="eyebrow">Paper Research Coach · {isKb ? "LEARN FROM MATERIALS" : "ANSWER ME WITH HTML"}</span>
        <h1>{isKb ? "把材料变成自己的知识" : "让解释可以看见、可以操作"}</h1>
        <p>{isKb ? "汇集资料，循着原文学习，在练习和追问中加深理解。" : "用图、公式、表格与互动问题展开解释，保留可继续修改的页面。"}</p>
      </div>
      <button className="primary" disabled={busy} onClick={() => isKb ? setNewKb(!newKb) : void create()}>
        <Plus size={16} />{isKb ? "新建知识库" : "新建讲解"}</button>
    </header>
    {error && <p role="alert">{error}</p>}
    {newKb && isKb && <form className="workspace-create" onSubmit={e => { e.preventDefault(); void create(); }}>
      <label>知识库名称<input autoFocus required value={title} onChange={e => setTitle(e.target.value)} placeholder="例如：卫星通信基础、论文方法比较" /></label>
      <label>学习深度<select value={depth} onChange={e => setDepth(e.target.value)}><option value="quick">快速概览</option><option value="systematic">系统学习</option></select></label>
      <button className="primary" disabled={busy || !title.trim()}>创建</button><button type="button" onClick={() => setNewKb(false)}>取消</button>
    </form>}
    <div className="workspace-layout">
      <aside className="workspace-library" aria-label={isKb ? "知识库列表" : "交互讲解列表"}>
        <div className="workspace-list-label">{isKb ? <Layers3 size={15} /> : <Sparkles size={15} />}{isKb ? "我的知识库" : "我的讲解"}<span>{rows.length}</span></div>
        {!rows.length && <p className="muted small">{isKb ? "新建知识库后，添加一份或多份资料。" : "点击新建讲解，写下你的问题。"}</p>}
        {rows.map((row: RecordData) => <button key={row.id} className={selected === row.id ? "current" : ""} onClick={() => (isKb ? setKb : setStudio)(row.id)}>
          <BookOpen size={15} /><div><strong>{row.title}</strong><small>{activeJob(state.jobs, row.id) ? "正在处理…" : row.published ? isKb ? `${row.materials.length} 份资料 · 可学习` : "页面已保存" : "草稿"}{row.needs_rebuild ? " · 待重建" : ""}</small></div></button>)}
        <p className="workspace-local">资料、学习记录与页面保存在本机。<br />生成和追问使用 Harness 登录账户。</p>
      </aside>
      <section className="workspace-main">
        {isKb ? kb ? <LearningWorkspace key={kb} id={kb} paper={paper} jobs={props.jobs} reload={reload} report={report} methodRequest={methodRequest} onNavigate={entry => { setKb(entry.kb_id); setMethodRequest({ ...entry, requested_at: Date.now() }); }} /> : <div className="workspace-empty"><Layers3 size={35} /><h2>从一组材料开始</h2><p>导入 PDF、Word、PPT、EPUB、Markdown 或文本，保留原文出处。</p><button onClick={() => setNewKb(true)}>新建知识库</button></div>
          : studio ? <InteractiveStudio key={studio} id={studio} paper={paper} page={page} quote={quote} kbs={state.kbs} {...props} /> : <div className="workspace-empty"><Sparkles size={35} /><h2>把一个问题展开</h2><p>可从当前论文或知识库中取材，也可以解释一个独立的问题。</p><button onClick={() => void create()}>新建交互式讲解</button></div>}
      </section>
    </div>
  </div>;
}

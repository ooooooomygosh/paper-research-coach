import React, { useCallback, useEffect, useRef, useState } from "react";
import { Code2, Download, Eye, Sparkles } from "./glyphs";
import ArtifactFrame from "./ArtifactFrame";
import { JobStatus } from "./Workspace";
import { activeJob, RecordData, versionQuery, workspaceApi, workspaceUrl } from "./workspace-api";

export default function InteractiveStudio({ id, jobs, kbs, paper, page, quote, reload, report, onSource }: {
  id: string; jobs: RecordData[]; kbs: RecordData[]; paper?: RecordData; page: number; quote?: string;
  reload: () => Promise<any>; report: (message: string) => void;
  onSource?: (anchor: any) => void;
}) {
  const [row, setRow] = useState<RecordData | null>(null), [draft, setDraft] = useState<RecordData>({});
  const [busy, setBusy] = useState(false), [editor, setEditor] = useState(false), [version, setVersion] = useState("");
  const [notice, setNotice] = useState("");
  const [requirementsOpen, setRequirementsOpen] = useState(false);
  const job = jobs.find(j => j.owner === id), running = !!activeJob(jobs, id), input = useRef<HTMLTextAreaElement>(null);
  const load = useCallback(async () => {
    const result = await workspaceApi(`/studios/${id}`);
    setRow(result); setDraft(result); return result;
  }, [id]);
  useEffect(() => { void load().catch(error => report(error.message)); }, [load]);
  const seenJob = useRef<string>("");
  useEffect(() => {
    const status = job?.id + ":" + job?.state;
    if (seenJob.current && seenJob.current !== status && job && !running) {
      setVersion(""); void load().catch(error => report(error.message));
    }
    seenJob.current = status;
  }, [job?.id, job?.state, running, load]);
  async function save() {
    const latest = await workspaceApi(`/studios/${id}`);
    const keys = ["title", "question", "source", "theme", "template", "language", "context", "presentation"];
    if (keys.some(key => JSON.stringify(latest[key]) !== JSON.stringify(row?.[key]))) throw new Error("讲解已在其他窗口更新，请重新打开后编辑。当前修改仍在编辑器中。");
    const next = await workspaceApi(`/studios/${id}`, { title: draft.title, question: draft.question, source: draft.source,
      theme: draft.theme, template: draft.template, language: draft.language, context: draft.context, presentation: draft.presentation || 'document', revision: latest.revision }, "PUT");
    setRow(next); setDraft(next); return next;
  }
  async function perform(action: "generate" | "render" | "save") {
    if (version) { report("历史版本仅供查看与导出，请返回当前草稿再编辑或生成。"); return; }
    setBusy(true); setNotice("");
    try {
      await save();
      if (action === "generate") await workspaceApi(`/studios/${id}/generate`, { question: draft.question });
      if (action === "render") { await workspaceApi(`/studios/${id}/render`, {}); setVersion(""); await load(); }
      if (action === "save") setNotice("草稿已保存。点击渲染可更新页面。");
      await reload();
    } catch (error) { report(String(error)); }
    finally { setBusy(false); }
  }
  function set(key: string, value: any) { setDraft(old => ({ ...old, [key]: value })); }
  function relay(text: string) {
    set("question", text); setNotice(version ? "历史页面输入已带回当前草稿。返回当前版后，请核对来源再发送。" : "页面输入已带回，可以修改后再点击生成。");
    setRequirementsOpen(true);
    requestAnimationFrame(() => { input.current?.scrollIntoView({ behavior: "smooth", block: "center" }); input.current?.focus(); });
  }
  if (!row) return <p role="status">正在打开讲解…</p>;
  const selectedContext = draft.context?.kb_id ? "kb:" + draft.context.kb_id : draft.context?.paper_id ? "paper" : "none";
  const publication = version ? row.history.find((p: RecordData) => p.version === version) || row.published : row.published;
  const changed = ["title", "source", "question", "theme", "template", "language", "context", "presentation"].some(key => JSON.stringify(draft[key]) !== JSON.stringify(row[key]));
  const components = draft.presentation === 'components';
  return <div className="studio-workspace">
    <div className="workspace-section-head"><h2>{row.title}</h2><span className="muted small">{changed ? "有未保存的修改" : row.published ? "本机已保存" : "待生成"}</span></div>
    {version && <p className="workspace-notice">历史版本仅供查看与导出。继续编辑和生成使用当前草稿及其来源。<button onClick={() => setVersion("")}>返回当前草稿</button></p>}
    {!version && <details className="studio-requirements" open={!row.published || requirementsOpen} onToggle={e => { if (row.published) setRequirementsOpen(e.currentTarget.open); }}>
    <summary>{row.published ? "修改讲解要求" : "生成讲解"}</summary>
    <label className="workspace-question">你想弄清楚什么？<textarea aria-label="交互式讲解问题" ref={input} value={draft.question || ""} disabled={running}
      onChange={e => set("question", e.target.value)} placeholder="例如：用图和一个可选分支解释这页论文的方法，并指出适用条件。" rows={3} /></label>
    <div className="workspace-controls">
      <label className="studio-output-form">讲解形式<select aria-label="讲解形式" disabled={running} value={draft.presentation || 'document'} onChange={e => { set('presentation', e.target.value); setEditor(false); }}>
        <option value="document">图文文档</option><option value="components">可操作组件</option>
      </select></label>
      <label>来源<select aria-label="讲解来源" disabled={running} value={selectedContext} onChange={e => {
        const value = e.target.value;
        set("context", value === "none" ? {} : value === "paper" ? { paper_id: paper?.id, source_version: paper?.source_version, page_index: page, quote } : { kb_id: value.slice(3), version: kbs.find(kb => kb.id === value.slice(3))?.published?.version });
      }}><option value="none">独立问题</option>{paper && <option value="paper">{draft.context?.paper_id === paper.id ? "已绑定论文 · 第 " + (draft.context.page_index + 1) + " 页" : "当前论文 · 第 " + (page + 1) + " 页"}</option>}
        {draft.context?.paper_id && draft.context.paper_id !== paper?.id && <option value="paper">已绑定的论文页</option>}
        {kbs.filter(kb => kb.published).map(kb => <option key={kb.id} value={"kb:" + kb.id}>{kb.title}</option>)}
      </select></label>
      {!components && <details><summary>文档外观</summary><label>主题<select value={draft.theme} disabled={running} onChange={e => set("theme", e.target.value)}><option value="paper">纸张</option><option value="blueprint">蓝图</option><option value="shadcn">简洁</option></select></label>
      <label>布局<select value={draft.template} disabled={running} onChange={e => set("template", e.target.value)}><option value="doc">阅读文档</option><option value="sheet">单页工作表</option></select></label></details>}
      <label>语言<select value={draft.language} disabled={running} onChange={e => set("language", e.target.value)}><option value="zh">中文</option><option value="en">English</option></select></label>
      {paper && <button disabled={running} onClick={() => set("context", { paper_id: paper.id, source_version: paper.source_version, page_index: page, quote })}>使用当前论文页</button>}
      <button className="primary" disabled={busy || running || !draft.question?.trim()} onClick={() => void perform("generate")}><Sparkles size={15} />{row.published ? "按要求更新讲解" : "生成交互式讲解"}</button>
    </div>
    <p className="muted small">使用 Harness 当前登录账户。{components ? '自动选择概念、步骤、比较、参数或证据组件；参数变化在本地计算。' : '页面回答与选择会带回提问区。'}点击生成后才发送。</p>
    </details>}
    <JobStatus job={job?.state === 'completed' ? undefined : job} onCancel={() => { void workspaceApi(`/jobs/${job!.id}/cancel`, {}).then(reload).catch(error => report(error.message)); }} />
    {notice && <p className="workspace-notice" role="status">{notice}</p>}
    <div className="workspace-artifact-actions">
      {!components && <button aria-pressed={editor} disabled={!!version} onClick={() => setEditor(!editor)}>{editor ? <Eye size={15} /> : <Code2 size={15} />}{editor ? "收起草稿" : "编辑 Markdown 草稿"}</button>}
      {row.published && <>
        <label>版本<select aria-label="讲解版本" value={version} onChange={e => setVersion(e.target.value)}><option value="">当前版本</option>{[...row.history].reverse().map((p: RecordData) => <option key={p.version} value={p.version}>{new Date(p.created_at).toLocaleString()}</option>)}</select></label>
        <a href={workspaceUrl(`/export/studio/${id}/page.html`) + versionQuery(publication.version)} download><Download size={14} />HTML</a>
        <a href={workspaceUrl(`/export/studio/${id}/page.md`) + versionQuery(publication.version)} download>Markdown</a>
        {publication.format === 'components' && <a href={workspaceUrl(`/export/studio/${id}/page.json`) + versionQuery(publication.version)} download>组件数据</a>}
      </>}
    </div>
    {editor && !version && !components && <div className="workspace-editor"><label>页面标题<input value={draft.title} disabled={running} onChange={e => set("title", e.target.value)} /></label>
      <label>可编辑草稿<textarea aria-label="交互页面 Markdown 草稿" className="workspace-code" value={draft.source} disabled={running} onChange={e => set("source", e.target.value)} rows={16} spellCheck={false} /></label>
      <div className="button-row"><button disabled={busy || running} onClick={() => void perform("save")}>保存草稿</button><button className="primary" disabled={busy || running || !draft.source?.trim()} onClick={() => void perform("render")}>保存并渲染</button></div>
    </div>}
    {publication?.warnings?.length > 0 && <details className="workspace-warnings"><summary>页面提示 · {publication.warnings.length}</summary><pre>{JSON.stringify(publication.warnings, null, 2)}</pre></details>}
    {publication ? <ArtifactFrame kind="studio" id={id} title={publication.title || row.title} version={publication.version} onQuestion={relay} report={report}
        onLocate={publication.source_anchor && onSource ? () => onSource(publication.source_anchor) : undefined} />
      : <div className="workspace-empty"><Sparkles size={30} /><h3>从一个问题开始</h3><p>{components ? '账户生成一个可操作组件，来源与交互状态一起保留。' : '写下问题后生成图文讲解，也可以编辑自己的 Markdown。'}</p>{!components && <button onClick={() => setEditor(true)}>打开草稿编辑器</button>}</div>}
  </div>;
}

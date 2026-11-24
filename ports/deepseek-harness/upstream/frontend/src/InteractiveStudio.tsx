import React, { useCallback, useEffect, useRef, useState } from "react";
import { Code2, Download, Eye, Sparkles } from "./glyphs";
import ArtifactFrame from "./ArtifactFrame";
import { JobStatus } from "./Workspace";
import { studioPaperContext } from "./studio-context";
import { RecordData, versionQuery, workspaceApi, workspaceUrl } from "./workspace-api";
import "./interactive-studio.css";

function sourceLabel(context: RecordData, papers: RecordData[], kbs: RecordData[]) {
  if (context.paper_id) {
    const title = papers.find(item => item.id === context.paper_id)?.title || "来源论文";
    return title + (Number.isInteger(context.page_index) ? " · PDF 第 " + (context.page_index + 1) + " 页" : "");
  }
  if (context.kb_id) return kbs.find(item => item.id === context.kb_id)?.title || "已绑定的知识库";
  return "独立问题";
}

const equal = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

export default function InteractiveStudio({ id, jobs, kbs, paper, page, papers, reload, report, onSource }: {
  id: string; jobs: RecordData[]; kbs: RecordData[]; paper?: RecordData; page: number; papers?: RecordData[];
  reload: () => Promise<any>; report: (message: string) => void;
  onSource?: (anchor: RecordData) => boolean | void;
}) {
  const [row, setRow] = useState<RecordData | null>(null);
  const [edits, setEdits] = useState<RecordData>({});
  const [busy, setBusy] = useState(false), [editor, setEditor] = useState(false), [version, setVersion] = useState("");
  const [notice, setNotice] = useState(""), [error, setError] = useState("");
  const [pendingQuestion, setPendingQuestion] = useState("");
  const [requirementsOpen, setRequirementsOpen] = useState(false);
  const [submitted, setSubmitted] = useState<RecordData | null>(null);
  const job = (submitted && jobs.find(job => job.id === submitted.id)) || submitted || jobs.find(job => job.owner === id);
  const running = job?.state === "queued" || job?.state === "running";
  const input = useRef<HTMLTextAreaElement>(null);
  const path = "/studios/" + id;
  const load = useCallback(async () => {
    const result = await workspaceApi(path);
    setRow(previous => previous && previous.revision > result.revision ? previous : result);
  }, [path]);
  useEffect(() => { void load().catch(error => setError(error.message)); }, [load]);
  // Only refresh draft data when a generation reaches a terminal state.
  const latestJob = useRef("");
  const jobKey = job ? job.id + ":" + job.state : "";
  useEffect(() => {
    if (latestJob.current && latestJob.current !== jobKey && jobKey && !running) {
      void load().catch(error => setError(error.message));
    }
    latestJob.current = jobKey;
  }, [jobKey, running, load]);
  useEffect(() => {
    if (submitted && jobs.some(job => job.id === submitted.id)) setSubmitted(null);
  }, [jobs, submitted]);
  const draft = { ...row, ...edits };
  const changes = Object.fromEntries(Object.entries(edits).filter(([key, value]) => !equal(row?.[key], value)));
  const changed = Object.keys(changes).length > 0;
  const recovering = !!job && ["failed", "cancelled", "interrupted"].includes(job.state);
  async function save() {
    if (!changed) return;
    const latest = await workspaceApi(path);
    const keys = Object.keys(changes);
    if (keys.some(key => !equal(latest[key], row?.[key]) && !equal(latest[key], changes[key]))) {
      throw new Error("草稿已在其他窗口更新。可以重新载入，同时保留此处的修改。");
    }
    const next = await workspaceApi(path, { ...changes, revision: latest.revision }, "PUT");
    setRow(next);
    setEdits(current => Object.fromEntries(Object.entries(current).filter(([key, value]) => !equal(value, edits[key]))));
  }
  async function perform(action: "generate" | "render" | "save") {
    if (busy || running || version) return;
    setBusy(true); setNotice(""); setError("");
    try {
      await save();
      if (action === "generate") {
        const accepted = await workspaceApi(path + "/generate", { question: draft.question });
        setSubmitted(accepted);
        setRequirementsOpen(false);
      }
      if (action === "render") setRow(await workspaceApi(path + "/render", {}));
      if (action === "save") setNotice("草稿已保存。");
      void reload().catch(error => report(error.message));
    } catch (error) { setError(error instanceof Error ? error.message : String(error)); }
    finally { setBusy(false); }
  }
  async function reloadDraft() {
    try { await load(); setError(""); }
    catch (error) { setError(error instanceof Error ? error.message : String(error)); }
  }
  function set(key: string, value: any) {
    setEdits(old => {
      if (!equal(row?.[key], value)) return { ...old, [key]: value };
      const next = { ...old };
      delete next[key];
      return next;
    });
  }
  function focusQuestion() {
    setVersion("");
    setRequirementsOpen(true);
    requestAnimationFrame(() => {
      input.current?.scrollIntoView?.({ behavior: "smooth", block: "center" });
      input.current?.focus({ preventScroll: true });
    });
  }
  function relay(text: string) {
    const question = text.trim();
    if (!question) return;
    if ("question" in changes && changes.question !== question) {
      setPendingQuestion(question);
      setRequirementsOpen(true);
      setVersion("");
      return;
    }
    set("question", question);
    setNotice(version ? "已带回历史页的提问。请核对当前草稿的来源后生成。" : "已带回提问，可以编辑后生成。");
    focusQuestion();
  }
  if (!row) return error ? <div className="workspace-notice" role="alert">{error} <button onClick={() => void reloadDraft()}>重试打开</button></div>
    : <p role="status">正在打开讲解…</p>;

  const currentSource = studioPaperContext(paper, page);
  const context = draft.context || {};
  const sourcePapers = papers || (paper ? [paper] : []);
  const boundPaper = sourcePapers.find(item => item.id === context.paper_id);
  const staleSource = boundPaper && context.source_version && context.source_version !== boundPaper.source_version;
  const latestKb = kbs.find(item => item.id === context.kb_id);
  const olderKb = latestKb?.published && context.version && latestKb.published.version !== context.version;
  const selectedContext = context.kb_id ? "kb:" + context.kb_id : context.paper_id ? "bound-paper" : "none";
  const publication = version ? row.history.find((p: RecordData) => p.version === version) || row.published : row.published;
  const components = draft.presentation === "components";
  const open = !row.published || requirementsOpen || recovering;
  const inputsBusy = busy || running;
  const samePage = context.paper_id === currentSource?.paper_id && context.source_version === currentSource?.source_version
    && context.page_index === currentSource?.page_index;
  const locate = (binding: RecordData) => onSource?.({ ...binding, status: "verified", rects: binding.rects || [] });

  return <div className="studio-workspace">
    <div className="workspace-section-head"><h2>{row.title}</h2>
      <span className="muted small">{changed ? "有未保存的修改" : row.published ? "本机已保存" : "草稿"}</span>
    </div>
    {version && <div className="workspace-notice">正在查看历史版本。<button onClick={() => { setVersion(""); setRequirementsOpen(true); }}>返回当前草稿</button></div>}
    {!version && <details className="studio-requirements" open={open} onToggle={e => {
      if (row.published && !recovering) setRequirementsOpen(e.currentTarget.open);
    }}>
      <summary>{row.published ? "继续提问或修改讲解" : "设置讲解问题"}</summary>
      <form onSubmit={e => { e.preventDefault(); void perform("generate"); }}>
        <div className="studio-source-card">
          <div className="studio-source-header">
            <div><span className="muted small">草稿来源</span><strong>{sourceLabel(context, sourcePapers, kbs)}</strong></div>
            {onSource && context.paper_id && !staleSource && Number.isInteger(context.page_index) && <button type="button" onClick={() => locate(context)}>回到来源页</button>}
            {currentSource && (!samePage || context.quote) && <button type="button" disabled={inputsBusy} onClick={() => set("context", currentSource)}>
              {samePage ? "改用整页" : "改用当前页"}
            </button>}
          </div>
          {context.quote && <details className="studio-quotation" open={!row.published || undefined}><summary>选中文字</summary><blockquote>{context.quote}</blockquote></details>}
          {staleSource && <p className="studio-source-warning" role="status">来源 PDF 已换版，请重新选择来源。</p>}
          {olderKb && <div className="studio-source-warning">已绑定知识库的旧发布版本。<button type="button" disabled={inputsBusy}
            onClick={() => set("context", { kb_id: latestKb.id, version: latestKb.published.version })}>切换到最新版本</button></div>}
        </div>
        {pendingQuestion && <div className="workspace-notice studio-incoming" role="status">
          <p>讲解页带回了一个新问题。当前问题仍在草稿中。</p><blockquote>{pendingQuestion}</blockquote>
          <button type="button" onClick={() => { set("question", pendingQuestion); setPendingQuestion(""); focusQuestion(); }}>使用新问题</button>
          <button type="button" onClick={() => setPendingQuestion("")}>保留当前问题</button>
        </div>}
        <label className="workspace-question">你想弄清楚什么？<textarea aria-label="交互式讲解问题" ref={input} value={draft.question || ""} maxLength={16000}
          onChange={e => set("question", e.target.value)} placeholder={context.quote ? "例如：这段话为什么成立？用一个可以操作的例子解释。" : "例如：这个方法有哪些步骤？我该核对什么条件？"} rows={3} /></label>
        {!draft.question?.trim() && <div className="studio-starters" aria-label="常见讲解问题">
          {[
            ["拆解机制", "请用可操作的步骤讲清核心机制，说明每一步的输入和结果。"],
            ["核对证据", "请设置一道判断题，帮助我检查证据支持什么结论，以及适用条件。"],
          ].map(([label, question]) => <button type="button" key={label} onClick={() => { set("question", question); focusQuestion(); }}>{label}</button>)}
        </div>}
        <div className="workspace-controls studio-options">
          <label>来源<select aria-label="讲解来源" disabled={inputsBusy} value={selectedContext} onChange={e => {
            const value = e.target.value;
            set("context", value === "none" ? {} : value === "current-paper" ? currentSource : {
              kb_id: value.slice(3), version: kbs.find(kb => kb.id === value.slice(3))?.published?.version,
            });
          }}>
            <option value="none">独立问题</option>
            {context.paper_id && <option value="bound-paper" disabled>{sourceLabel(context, sourcePapers, kbs)}</option>}
            {currentSource && !samePage && <option value="current-paper">当前 PDF 第 {page + 1} 页</option>}
            {context.kb_id && !latestKb?.published && <option value={selectedContext} disabled>已绑定的知识库</option>}
            {kbs.filter(kb => kb.published).map(kb => <option key={kb.id} value={"kb:" + kb.id}>{kb.title}</option>)}
          </select></label>
          <label>讲解形式<select aria-label="讲解形式" disabled={inputsBusy} value={draft.presentation || "document"} onChange={e => { set("presentation", e.target.value); setEditor(false); }}>
            <option value="components">可操作组件</option><option value="document">图文文档</option>
          </select></label>
          <details className="studio-advanced"><summary>语言与外观</summary><div>
            <label>语言<select value={draft.language} disabled={inputsBusy} onChange={e => set("language", e.target.value)}><option value="zh">中文</option><option value="en">English</option></select></label>
            {!components && <><label>主题<select value={draft.theme} disabled={inputsBusy} onChange={e => set("theme", e.target.value)}><option value="paper">纸张</option><option value="blueprint">蓝图</option><option value="shadcn">简洁</option></select></label>
              <label>布局<select value={draft.template} disabled={inputsBusy} onChange={e => set("template", e.target.value)}><option value="doc">阅读文档</option><option value="sheet">单页工作表</option></select></label></>}
          </div></details>
        </div>
        <div className="studio-submit">
          <button type="submit" className="primary" disabled={inputsBusy || staleSource || !draft.question?.trim()}><Sparkles size={15} />
            {running ? "讲解生成中…" : recovering ? "重新生成" : row.published ? "按要求更新讲解" : "生成交互式讲解"}
          </button>
          <button type="button" disabled={inputsBusy || !changed} onClick={() => void perform("save")}>保存草稿</button>
          <span className="muted small">生成时使用 Harness 登录账户。</span>
        </div>
      </form>
    </details>}
    <JobStatus job={job?.state === "completed" ? undefined : job} onCancel={() => {
      if (!job) return;
      void workspaceApi("/jobs/" + job.id + "/cancel", {}).then(setSubmitted).then(reload).catch(error => setError(error.message));
    }} />
    {error && <div className="workspace-notice" role="alert">{error} <button onClick={() => void reloadDraft()}>重新载入草稿</button></div>}
    {notice && <p className="workspace-notice" role="status">{notice}</p>}
    <div className="workspace-artifact-actions">
      {!components && <button aria-pressed={editor} disabled={!!version} onClick={() => setEditor(!editor)}>{editor ? <Eye size={15} /> : <Code2 size={15} />}{editor ? "收起草稿" : "编辑 Markdown 草稿"}</button>}
      {publication && <>
        <label>版本<select aria-label="讲解版本" value={version} onChange={e => setVersion(e.target.value)}><option value="">当前版本</option>{[...row.history].reverse().map((p: RecordData) => <option key={p.version} value={p.version}>{new Date(p.created_at).toLocaleString()}</option>)}</select></label>
        <a href={workspaceUrl("/export/studio/" + id + "/page.html") + versionQuery(publication.version)} download><Download size={14} />HTML</a>
        <a href={workspaceUrl("/export/studio/" + id + "/page.md") + versionQuery(publication.version)} download>Markdown</a>
        {publication.format === "components" && <a href={workspaceUrl("/export/studio/" + id + "/page.json") + versionQuery(publication.version)} download>组件数据</a>}
      </>}
    </div>
    {editor && !version && !components && <div className="workspace-editor">
      <label>页面标题<input value={draft.title} disabled={inputsBusy} onChange={e => set("title", e.target.value)} /></label>
      <label>可编辑草稿<textarea aria-label="交互页面 Markdown 草稿" className="workspace-code" value={draft.source} disabled={inputsBusy} onChange={e => set("source", e.target.value)} rows={16} spellCheck={false} /></label>
      <div className="button-row"><button disabled={inputsBusy || !changed} onClick={() => void perform("save")}>保存 Markdown 草稿</button>
        <button className="primary" disabled={inputsBusy || !draft.source?.trim()} onClick={() => void perform("render")}>保存并渲染</button></div>
    </div>}
    {publication?.warnings?.length > 0 && <details className="workspace-warnings"><summary>页面提示 · {publication.warnings.length}</summary><pre>{JSON.stringify(publication.warnings, null, 2)}</pre></details>}
    {publication && <div className="studio-result">
      <div className="studio-result-source"><span>{publication.context ? "页面来源 · " + sourceLabel(publication.context, sourcePapers, kbs) : "页面来源未记录"}</span>
        {publication.source_anchor && onSource && <button onClick={() => locate(publication.source_anchor)}>查看页面来源</button>}
      </div>
      <ArtifactFrame kind="studio" id={id} title={publication.title || row.title} version={publication.version} onQuestion={relay} report={report}
        onLocate={publication.source_anchor && onSource ? () => locate(publication.source_anchor) : undefined} />
    </div>}
  </div>;
}

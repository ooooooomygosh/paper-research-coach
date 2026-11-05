import React, { useCallback, useEffect, useRef, useState } from "react";
import { ArrowUp, Download, FileText, FolderPlus, MessageCircle, Upload } from "lucide-react";
import ArtifactFrame from "./ArtifactFrame";
import MethodsLibrary from "./MethodsLibrary";
import { JobStatus } from "./Workspace";
import { activeJob, RecordData, unitProgress, uploadMaterial, versionQuery, workspaceApi, workspaceUrl } from "./workspace-api";

function UnitNote({ unit, progress, onSave }: { unit: RecordData; progress?: RecordData; onSave: (value: RecordData) => Promise<void> }) {
  const [note, setNote] = useState(progress?.note || ""), [completed, setCompleted] = useState(!!progress?.completed);
  const [saving, setSaving] = useState(false), [saved, setSaved] = useState(false);
  return <div className="workspace-unit-note"><label className="workspace-inline"><input type="checkbox" checked={completed} onChange={e => { setCompleted(e.target.checked); setSaved(false); }} />我已学习此单元</label>
    <textarea aria-label={"学习笔记 " + unit.title} value={note} onChange={e => { setNote(e.target.value); setSaved(false); }} placeholder="用自己的话解释这一点，记下疑问或应用想法…" rows={3} />
    <button disabled={saving} onClick={async () => { setSaving(true); try { await onSave({ unit_id: unit.id, note, completed }); setSaved(true); } finally { setSaving(false); } }}>保存笔记与进度</button>
    {saved && <span role="status" className="muted small">已保存</span>}
  </div>;
}

function Exercise({ item, attempt, submit, onSource }: { item: RecordData; attempt?: RecordData; submit: (answer: number) => Promise<void>; onSource: () => void }) {
  const [answer, setAnswer] = useState<number | null>(null), [busy, setBusy] = useState(false);
  return <article className="workspace-exercise"><span className="eyebrow">{item.ability} · 模型编制练习</span><h4>{item.question}</h4>
    {item.options.map((option: string, index: number) => <label key={index}><input type="radio" name={item.id} checked={answer === index} onChange={() => setAnswer(index)} />{String.fromCharCode(65 + index)}. {option}</label>)}
    <button disabled={busy || answer === null} onClick={async () => { setBusy(true); try { await submit(answer!); } finally { setBusy(false); } }}>核对参考答案</button>
    {attempt && <div className={"workspace-answer " + (attempt.correct ? "correct" : "retry")} role="status"><strong>{attempt.correct ? "与参考答案一致" : "再回到原文看看"} · 参考 {String.fromCharCode(65 + attempt.reference_answer)}</strong><p>{attempt.explanation}</p><blockquote>{attempt.quote}</blockquote><button onClick={onSource}>{attempt.source} · 查看来源</button><small>{attempt.notice}</small></div>}
  </article>;
}

export default function LearningWorkspace({ id, paper, jobs, reload, report, methodRequest, onNavigate }: {
  id: string; paper?: RecordData; jobs: RecordData[]; reload: () => Promise<any>; report: (message: string) => void;
  methodRequest?: RecordData | null; onNavigate?: (entry: RecordData) => void;
}) {
  const [row, setRow] = useState<RecordData | null>(null), [tab, setTab] = useState("page"), [version, setVersion] = useState("");
  const [busy, setBusy] = useState(false), [question, setQuestion] = useState(""), [unit, setUnit] = useState("");
  const [method, setMethod] = useState<RecordData | null>(null), [source, setSource] = useState<RecordData | null>(null);
  const [wrongOnly, setWrongOnly] = useState(false), [notice, setNotice] = useState("");
  const compose = useRef<HTMLTextAreaElement>(null), upload = useRef<HTMLInputElement>(null), sourceBox = useRef<HTMLDivElement>(null);
  const job = jobs.find(j => j.owner === id), running = !!activeJob(jobs, id), jobState = job?.id + ":" + job?.state;
  const load = useCallback(async () => { const next = await workspaceApi(`/kbs/${id}` + versionQuery(version)); setRow(next); return next; }, [id, version]);
  useEffect(() => { void load().catch(error => report(error.message)); }, [load]);
  const seenJob = useRef("");
  useEffect(() => {
    if (seenJob.current && seenJob.current !== jobState && job && !running) {
      void load().then(next => { if (next.published) setTab(old => old === "materials" ? "page" : old); }).catch(error => report(error.message));
    }
    seenJob.current = jobState;
  }, [jobState, running, load]);
  useEffect(() => {
    if (methodRequest?.kb_id === id) applyMethod(methodRequest);
  }, [methodRequest?.ref, methodRequest?.requested_at, id]);
  async function action(task: () => Promise<any>) {
    setBusy(true); setNotice("");
    try { await task(); await load(); await reload(); }
    catch (error) { report(String(error)); }
    finally { setBusy(false); }
  }
  function relay(text: string, context?: { unit_id?: string; method_id?: string }) {
    if (context?.unit_id && row?.page?.contentUnits.some((item: RecordData) => item.id === context.unit_id)) { setUnit(context.unit_id); setMethod(null); }
    if (context?.method_id) { const card = row?.page?.methodLibrary?.methods.find((item: RecordData) => item.id === context.method_id); if (card) { setMethod(card); setUnit(""); } }
    setQuestion(text); setNotice("已带回提问区，请确认或修改后发送。");
    compose.current?.scrollIntoView({ behavior: "smooth", block: "center" }); compose.current?.focus();
  }
  function applyMethod(entry: RecordData) {
    if (entry.kb_id !== id) { onNavigate?.(entry); return; }
    setVersion(""); setMethod(entry.card); setUnit("");
    relay("请用“" + entry.card.name + "”分析下面的问题，先核对前提与限制：\n我的问题是：");
  }
  async function showSource(blockId: string, selectedVersion?: string) {
    try { setSource(await workspaceApi(`/kbs/${id}/sources/${blockId}` + versionQuery(selectedVersion || row?.viewing?.version))); requestAnimationFrame(() => sourceBox.current?.scrollIntoView({ behavior: "smooth", block: "nearest" })); }
    catch (error) { report(String(error)); }
  }
  async function ask() {
    if (!question.trim()) return;
    await action(() => workspaceApi(`/kbs/${id}/ask`, { question, unit_id: unit || undefined, method_id: method?.id, version: row?.viewing?.version }));
  }
  async function files(selected: FileList | null) {
    if (!selected?.length) return;
    const list = Array.from(selected);
    await action(async () => { for (const file of list) { await uploadMaterial(id, file); } setNotice(`已添加 ${list.length} 份资料，点击构建开始整理。`); });
    if (upload.current) upload.current.value = "";
  }
  if (!row) return <p role="status">正在打开知识库…</p>;
  const viewing = row.viewing, currentVersion = viewing?.version;
  const units: RecordData[] = row.page?.contentUnits || [], questions: RecordData[] = row.questions || [];
  const chat = row.chat.filter((turn: RecordData) => turn.version === currentVersion);
  const latestAttempts: RecordData = {};
  for (const attempt of row.attempts || []) if (!latestAttempts[attempt.question_id]) latestAttempts[attempt.question_id] = attempt;
  const blockFor = (unitId: string) => questions.find(item => item.unit_id === unitId)?.block_id;
  const exercises = questions.filter(item => (!unit || item.unit_id === unit) && (!wrongOnly || latestAttempts[item.id] && !latestAttempts[item.id].correct));
  const completed = units.filter(item => unitProgress(row.progress, item.id, currentVersion)?.completed).length;
  return <div className="learning-workspace">
    <div className="workspace-section-head"><div><h2>{row.title}</h2><span className="muted small">{row.materials.length} 份材料{viewing ? ` · ${units.length} 个学习单元 · 已学习 ${completed}` : " · 待构建"}</span></div>
      <button onClick={() => setTab("materials")}><FolderPlus size={15} />资料与构建</button></div>
    {row.needs_rebuild && <p className="workspace-notice">资料或设置已变化。当前展示已发布的旧版；重新构建成功后才切换到新版。</p>}
    <JobStatus job={job} onCancel={() => { void action(() => workspaceApi(`/jobs/${job!.id}/cancel`, {})); }} />
    <nav className="workspace-tabs" aria-label="知识库功能">{[["page", "学习页面"], ["units", "单元与练习"], ["methods", "方法库"], ["materials", "资料与构建"]].map(([value, label]) => <button key={value} aria-pressed={tab === value} onClick={() => setTab(value)}>{label}</button>)}</nav>
    {viewing && <div className="workspace-artifact-actions"><label>学习版本<select aria-label="知识库学习版本" value={version} disabled={running} onChange={e => { setVersion(e.target.value); setUnit(""); setMethod(null); setSource(null); }}><option value="">当前发布版本</option>{[...row.history].reverse().map((p: RecordData) => <option key={p.version} value={p.version}>{new Date(p.created_at).toLocaleString()}</option>)}</select></label>
      <a href={workspaceUrl(`/export/kb/${id}/page.html`) + versionQuery(currentVersion)} download><Download size={14} />HTML</a>
      <a href={workspaceUrl(`/export/kb/${id}/page.md`) + versionQuery(currentVersion)} download>Markdown</a>
      <a href={workspaceUrl(`/export/kb/${id}/knowledge.zip`) + versionQuery(currentVersion)} download>知识库 ZIP（含原文提取）</a>
    </div>}
    {tab === "materials" && <div className="workspace-materials">
      <p className="muted">添加资料只保存在本机。点击构建后，提取的内容会交给 Harness 登录账户整理；长材料会产生多次请求。</p>
      <div className="workspace-controls"><button className="primary" disabled={busy || running} onClick={() => upload.current?.click()}><Upload size={15} />添加资料</button>
        <input ref={upload} type="file" multiple accept=".pdf,.docx,.pptx,.pptm,.epub,.md,.markdown,.txt,.html,.htm,.rtf,.mobi,.azw,.azw3" hidden aria-label="添加知识库材料" onChange={e => void files(e.target.files)} />
        {paper && <button disabled={busy || running} title={paper.title} onClick={() => void action(() => workspaceApi(`/kbs/${id}/from-paper`, { paper_id: paper.id }))}>加入当前论文</button>}
        <label>学习深度<select value={row.depth} disabled={busy || running} onChange={e => void action(() => workspaceApi(`/kbs/${id}`, { depth: e.target.value }, "PUT"))}><option value="quick">快速概览</option><option value="systematic">系统学习</option></select></label>
        <label>语言<select value={row.language} disabled={busy || running} onChange={e => void action(() => workspaceApi(`/kbs/${id}`, { language: e.target.value }, "PUT"))}><option value="zh">中文</option><option value="en">English</option></select></label>
      </div>
      <ul className="workspace-files">{row.materials.map((file: RecordData) => <li key={file.id}><FileText size={16} /><strong>{file.filename}</strong><span>{(file.size / 1024).toFixed(1)} KB</span>{file.paper_id && <small>来自论文库</small>}</li>)}</ul>
      {!row.materials.length && <div className="workspace-empty"><Upload size={28} /><p>添加一份或多份资料，或加入当前正在读的论文。</p></div>}
      <div className="button-row"><button className="primary" disabled={busy || running || !row.materials.length} onClick={() => void action(() => workspaceApi(`/kbs/${id}/build`, { resume: false }))}>{row.published ? "重新构建学习版" : "构建知识库并生成学习页"}</button>
        {job?.kind === "learning" && ["failed", "cancelled", "interrupted"].includes(job.state) && <button disabled={busy || running} onClick={() => void action(() => workspaceApi(`/kbs/${id}/build`, { resume: true }))}>从已完成的片段继续</button>}</div>
      <p className="muted small">支持文本型 PDF、Office、EPUB、HTML 和文本。扫描页及图中细节需要另行核对；MOBI / AZW 需要本机已有 Calibre。</p>
      {row.coverage && <details className="workspace-coverage" open><summary>此版本的处理记录</summary><p>{row.coverage.processed_blocks} / {row.coverage.total_blocks} 个提取片段已整理，其中 {row.coverage.content_blocks} 段生成正文单元。</p>
        <p>引文经过逐字匹配。覆盖统计表示实际处理范围；语义完整性未获独立审查。</p>{row.coverage.warnings.map((warning: string, i: number) => <p key={i} className="workspace-notice">{warning}</p>)}
        <details><summary>全部片段去向</summary>{row.coverage.dispositions.map((item: RecordData) => <p key={item.block_id}>{item.role === "content" ? "正文" : item.role === "structure" ? "结构信息" : "参考文献"} · {item.reason}<button className="text-button" onClick={() => void showSource(item.block_id)}>查看原文</button></p>)}</details>
      </details>}
    </div>}
    {tab === "page" && (viewing ? <ArtifactFrame kind="kb" id={id} title={row.title + " · 交互学习页"} version={currentVersion} onQuestion={relay} report={report} />
      : <div className="workspace-empty"><FileText size={30} /><h3>资料会成为一份可以反复学习的页面</h3><p>保留原项目六个学习模块、概念图、主题切换和笔记。</p><button onClick={() => setTab("materials")}>添加资料并构建</button></div>)}
    {tab === "units" && viewing && <div className="workspace-units">
      <div className="workspace-controls"><label>学习单元<select aria-label="当前学习单元" value={unit} onChange={e => { setUnit(e.target.value); setMethod(null); }}><option value="">全部单元</option>{units.map(item => <option key={item.id} value={item.id}>{item.label} · {item.title}</option>)}</select></label>
        <label className="workspace-inline"><input type="checkbox" checked={wrongOnly} onChange={e => setWrongOnly(e.target.checked)} />只看待复习的错题</label></div>
      {units.filter(item => !unit || item.id === unit).map(item => <article className="workspace-unit" key={currentVersion + item.id}><span className="eyebrow">{item.label}</span><h3>{item.title}</h3><p>{item.core}</p><ul>{item.takeaways.map((text: string, i: number) => <li key={i}>{text}</li>)}</ul>
        <button onClick={() => void showSource(blockFor(item.id))}>{item.source} · 查看原文</button>
        <UnitNote unit={item} progress={unitProgress(row.progress, item.id, currentVersion)} onSave={async value => { try { await workspaceApi(`/kbs/${id}/progress`, { ...value, version: currentVersion }, "PUT"); await load(); } catch (error) { report(String(error)); throw error; } }} />
      </article>)}
      <h3>练习与复习</h3><p className="muted small">练习及参考答案由模型编制，请同时核对材料。错题按最近一次作答记录筛选。</p>
      {exercises.map(item => <Exercise key={currentVersion + item.id} item={item} attempt={latestAttempts[item.id]} onSource={() => void showSource(item.block_id)} submit={async answer => { await action(() => workspaceApi(`/kbs/${id}/attempts`, { question_id: item.id, answer, version: currentVersion })); }} />)}
      {!exercises.length && <p className="workspace-notice">当前筛选下没有练习。</p>}
    </div>}
    {tab === "methods" && <MethodsLibrary kbId={id} refreshKey={currentVersion || ""} onApply={applyMethod} report={report} />}
    {source && <div className="workspace-source" ref={sourceBox}><div className="workspace-section-head"><h3>原文 · {source.source}</h3><button onClick={() => setSource(null)}>收起</button></div><pre>{source.text}</pre><small>对应本学习版本的提取片段，保留原始定位；图像与版面请回到原文件核对。</small></div>}
    {viewing && <section className="workspace-coach" aria-label="知识库学习教练"><div className="workspace-section-head"><h3><MessageCircle size={17} />基于资料继续问</h3><span className="muted small">{method ? "方法应用 · " + method.name : unit ? "当前单元" : "当前版本知识库"}</span></div>
      <div className="workspace-chat">{chat.map((turn: RecordData) => <article key={turn.id} className={turn.role}><strong>{turn.role === "user" ? "我" : "学习教练"}{turn.coverage === "not-covered" ? " · 本次检索未找到依据" : turn.coverage === "partial" ? " · 本次检索部分有据" : ""}</strong><p>{turn.content}</p>
        {turn.added_explanation && <aside><b>补充解释</b><p>{turn.added_explanation}</p></aside>}
        {turn.citations?.map((citation: RecordData, i: number) => <blockquote key={i}>{citation.quote}<button onClick={() => void showSource(citation.block_id, turn.version)}>{citation.source} · 查看原文</button></blockquote>)}
        {turn.coverage === "not-covered" && turn.retrieved_sources && <details><summary>查看本次检索范围；可选具体单元重问</summary>{turn.retrieved_sources.map((item: RecordData) => <button key={item.block_id} onClick={() => void showSource(item.block_id, turn.version)}>{item.source}</button>)}</details>}
      </article>)}</div>
      {notice && <p className="workspace-notice" role="status">{notice}</p>}
      {method && <p className="muted small">应用方法时先核对前提。<button className="text-button" onClick={() => setMethod(null)}>取消方法范围</button></p>}
      <textarea aria-label="知识库学习问题" ref={compose} value={question} onChange={e => setQuestion(e.target.value)} placeholder="针对原文提问，或把页面中的内容带回来继续讨论…" rows={3} />
      <div className="workspace-section-head"><small className="muted">回答限于本次检索片段；可选具体单元缩小范围。</small><button className="primary" disabled={busy || running || !question.trim()} onClick={() => void ask()}><ArrowUp size={15} />发送给学习教练</button></div>
    </section>}
  </div>;
}

import React, { useEffect, useState, useRef } from 'react';
import { id as operationId } from './api';
import { workspaceApi, workspaceUrl } from './workspace-api';

export function studyMessage(event: MessageEvent, source: Window | null, study: any) {
  const data = event.data;
  if (!source || event.source !== source || !study || !data || data.channel !== 'prc-study-v1' || data.id !== study.id || data.revision !== study.revision) return null;
  return study.paragraphs.find((p: any) => p.id === data.anchor_id)?.anchor || null;
}

/** A paragraph study references the existing paper and note records. */
export default function PaperStudy({ paperId, pageIndex = 0, quote = '', onLocate }: { paperId: string; pageIndex?: number; quote?: string; onLocate?: (anchor: any) => void }) {
  const frame = useRef<HTMLIFrameElement>(null);
  const [analysisDrafts, setAnalysisDrafts] = useState<Record<string, any>>({});
  const [noteDrafts, setNoteDrafts] = useState<Record<string, string>>({});
  const [rows, setRows] = useState<any[]>([]), [active, setActive] = useState<any>(null);
  const [indexing, setIndexing] = useState(false);
  const [scope, setScope] = useState('chapter'), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  useEffect(() => {
    const receive = (event: MessageEvent) => {
      const anchor = studyMessage(event, frame.current?.contentWindow || null, active);
      if (anchor) onLocate?.(anchor);
    };
    window.addEventListener('message', receive);
    return () => window.removeEventListener('message', receive);
  }, [active, onLocate]);
  async function saveNote(note: any) {
    try {
      await workspaceApi('/studies/' + active.id + '/notes/' + note.id, {content: noteDrafts[note.id] ?? note.content, revision: note.revision, operation_id: operationId()}, 'PUT');
      setActive(await workspaceApi('/studies/' + active.id));
      setNoteDrafts(previous => { const next = { ...previous }; delete next[note.id]; return next; });
    } catch (e: any) { setError(e.message); }
  }
  async function reviseAnalysis(paragraphId: string) {
    try {
      await workspaceApi('/studies/' + active.id + '/paragraph/' + paragraphId, {revision: active.revision, analysis: {...active.analyses[paragraphId], ...analysisDrafts[paragraphId]}}, 'PUT');
      setActive(await workspaceApi('/studies/' + active.id));
      setAnalysisDrafts(d => { const next = {...d}; delete next[paragraphId]; return next; });
    } catch (e: any) { setError(e.message); }
  }
  const reload = async () => {
    const all = await workspaceApi('/studies');
    setRows(all.filter((r: any) => r.paper_id === paperId));
  };
  useEffect(() => { setActive(null); setBusy(false); void reload().catch(e => setError(e.message)); }, [paperId]);
  useEffect(() => {
    if (!busy || !active) return;
    let cancelled = false;
    const timer = window.setInterval(async () => {
      try {
        const [row, state] = await Promise.all([workspaceApi('/studies/' + active.id), workspaceApi('')]);
        if (cancelled) return;
        setActive(row);
        const job = state.jobs.find((j: any) => j.owner === active.id);
        if (job && !['queued', 'running'].includes(job.state)) {
          setBusy(false); setError(job.message || ''); void reload();
        }
      } catch (e: any) { if (!cancelled) { setError(e.message); setBusy(false); } }
    }, 1500);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [busy, active?.id]);
  async function create() {
    try { setIndexing(true); setError(''); const row = await workspaceApi('/studies', { paper_id: paperId, page_index: pageIndex, scope, quote }, 'POST'); setActive(row); await reload(); }
    catch (e: any) { setError(e.message); } finally { setIndexing(false); }
  }
  async function generate() {
    try { setError(''); await workspaceApi('/studies/' + active.id + '/generate', {}, 'POST'); setBusy(true); }
    catch (e: any) { setError(e.message); }
  }
  async function stop() {
    try { const state = await workspaceApi(''); const job = state.jobs.find((j: any) => j.owner === active.id && ['queued', 'running'].includes(j.state)); if (job) await workspaceApi('/jobs/' + job.id + '/cancel', {}, 'POST'); setBusy(false); }
    catch (e: any) { setError(e.message); }
  }
  return <section aria-label="论文对照批注">
    <h2>论文对照批注</h2>
    <label>范围 <select value={scope} onChange={e => setScope(e.target.value)}><option value="selection">选段</option><option value="chapter">当前章节</option><option value="full">全文</option></select></label>
    <button onClick={() => void create()} disabled={busy || indexing}>{indexing ? "正在索引原文…" : "建立原文索引"}</button>
    <select aria-label="已保存研读材料" value={active?.id || ''} onChange={e => { const value = e.target.value; if (!value) setActive(null); else void workspaceApi('/studies/' + value).then(setActive).catch(error => setError(error.message)); }}><option value="">选择研读材料</option>{rows.map(r => <option key={r.id} value={r.id}>{r.title} · {r.scope}</option>)}</select>
    {error && <p role="alert">{error}</p>}
    {active && <><p>已分析 {Object.keys(active.analyses).length}/{active.paragraphs.length} 段；无文字层 {active.unreadable_pages.length} 页。模型分析不代表已掌握。</p>
      <button disabled={busy} onClick={() => void generate()}>继续翻译与分析</button>{busy && <button onClick={() => void stop()}>停止</button>}
      {onLocate && <details><summary>段落依据</summary>{active.paragraphs.map((p: any) => <button key={p.id} onClick={() => onLocate(p.anchor)}>{p.section} · PDF {p.anchor.page_index + 1}</button>)}</details>}
      <a href={workspaceUrl('/studies/' + active.id + '/html')} download={active.title + '.html'}>下载离线 HTML</a>
      <details><summary>修订译文与分析</summary>{active.paragraphs.filter((p: any) => active.analyses[p.id]).map((p: any) => <details key={p.id}><summary>{p.section} · PDF {p.anchor.page_index + 1}</summary>{([['translation','中文译文'],['function','段落功能'],['role','逻辑角色'],['critique','待核查处']] as const).map(([key,label]) => <label key={key}>{label}<textarea value={analysisDrafts[p.id]?.[key] ?? active.analyses[p.id][key]} onChange={e => setAnalysisDrafts(d => ({...d,[p.id]:{...d[p.id],[key]:e.target.value}}))} /></label>)}<button disabled={busy} onClick={() => void reviseAnalysis(p.id)}>保存修订</button></details>)}</details>
      <details><summary>本篇用户批注（共用原记录）</summary>{(active.notes || []).filter((n: any) => n.author === 'user').map((n: any) => <div key={n.id}><textarea aria-label="修改批注" value={noteDrafts[n.id] ?? n.content} onChange={e => setNoteDrafts(d => ({...d, [n.id]: e.target.value}))} /><button onClick={() => void saveNote(n)}>保存批注</button></div>)}</details>
      <iframe ref={frame} title="论文对照批注预览" sandbox="allow-scripts" src={workspaceUrl('/studies/' + active.id + '/html') + '?revision=' + active.revision + '&notes=' + encodeURIComponent((active.notes || []).map((n: any) => n.id + ':' + n.revision).join(','))} style={{ width: '100%', height: '75dvh', border: 0 }} />
    </>}
  </section>;
}

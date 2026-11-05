import React, { useEffect, useState } from "react";
import { RecordData, workspaceApi } from "./workspace-api";

export default function MethodsLibrary({ kbId, refreshKey, onApply, report }: {
  kbId: string; refreshKey: string; onApply: (entry: RecordData) => void; report: (message: string) => void;
}) {
  const [entries, setEntries] = useState<RecordData[]>([]), [query, setQuery] = useState("");
  const [all, setAll] = useState(false), [compare, setCompare] = useState<string[]>([]);
  async function search(q = query) {
    const result = await workspaceApi("/methods?q=" + encodeURIComponent(q)); setEntries(result.methods);
  }
  useEffect(() => { void search("").catch(error => report(error.message)); }, [kbId, refreshKey]);
  const visible = entries.filter(entry => all || entry.kb_id === kbId), selected = entries.filter(entry => compare.includes(entry.ref));
  return <div className="workspace-methods">
    <div className="workspace-section-head"><div><h3>可复用的方法</h3><p className="muted small">来源方法保留前提、限制、出处与版本。页面中的“理解”节点用于解释概念。</p></div></div>
    <p className="muted small">方法搜索使用各知识库当前发布版，应用时会打开该版本。历史方法保留在对应学习页与导出文件中。</p>
    <form className="workspace-search" onSubmit={e => { e.preventDefault(); void search().catch(error => report(error.message)); }}>
      <input aria-label="搜索知识库方法" placeholder="按问题、名称或标签搜索" value={query} onChange={e => setQuery(e.target.value)} />
      <button>搜索</button><label className="workspace-inline"><input type="checkbox" checked={all} onChange={e => setAll(e.target.checked)} />跨知识库</label>
    </form>
    {!!selected.length && <div className="workspace-comparison"><h3>方法对比</h3><div className="workspace-compare-grid">{selected.map(entry => <div key={entry.ref}><strong>{entry.card.name}</strong><p>{entry.card.problem}</p><b>适用条件</b><p>{entry.card.when}</p><b>前提</b><ul>{entry.card.prerequisites.map((text: string, i: number) => <li key={i}>{text}</li>)}</ul><b>限制</b><ul>{entry.card.limitations.map((text: string, i: number) => <li key={i}>{text}</li>)}</ul><small>{entry.title} · v{entry.card.version}</small></div>)}</div><button onClick={() => setCompare([])}>清除对比</button></div>}
    {!visible.length && <p className="workspace-notice">当前范围没有可复用的方法。知识概念会保留在学习页中。</p>}
    <div className="workspace-card-grid">{visible.map(entry => {
      const method = entry.card;
      return <article className="workspace-method-card" key={entry.ref}>
        <div className="workspace-section-head"><span className="eyebrow">{method.kind === "rule" ? "行动规则" : "方法框架"} · v{method.version}</span>
          <label className="workspace-inline"><input type="checkbox" aria-label={"对比方法 " + method.name} checked={compare.includes(entry.ref)} disabled={!compare.includes(entry.ref) && compare.length >= 2} onChange={e => setCompare(e.target.checked ? [...compare, entry.ref] : compare.filter(ref => ref !== entry.ref))} />对比</label></div>
        <h3>{method.name}</h3><p>{method.summary}</p><p><b>适用于：</b>{method.when}</p>
        <details><summary>步骤、边界与原文依据</summary><p><b>要解决的问题：</b>{method.problem}</p>
          <h4>前提</h4><ul>{method.prerequisites.map((text: string, i: number) => <li key={i}>{text}</li>)}</ul>
          <ol>{method.steps.map((step: RecordData, i: number) => <li key={i}><b>{step.action}</b><p>输入：{step.input}<br />产出：{step.output}<br />检查：{step.check}</p></li>)}</ol>
          <h4>限制</h4><ul>{method.limitations.map((text: string, i: number) => <li key={i}>{text}</li>)}</ul>
          <p>{method.rationale}</p>{method.sources.map((source: RecordData, i: number) => <blockquote key={i}>{source.quote}<cite>{source.locator}</cite></blockquote>)}
        </details>
        <small>{entry.title} · {method.evidence === "material" ? "来源材料" : method.evidence === "inference" ? "推断" : "综合"}</small>
        <button onClick={() => onApply(entry)}>用这个方法分析问题</button>
      </article>;
    })}</div>
  </div>;
}

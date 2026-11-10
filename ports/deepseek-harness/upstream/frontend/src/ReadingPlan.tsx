import { useState } from "react";
import { api, id } from "./api";
export default function ReadingPlan({ plan, paperId, onChange }: { plan: any; paperId: string; onChange: () => void }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  async function act(action: string, extra: object = {}) {
    setBusy(true); setError("");
    try { await api(`reading/${paperId}/plan`, { action, expected_revision: plan.revision, operation_id: id(), ...extra }); onChange(); }
    catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  return <section className="reading-plan-v2" aria-label="分层阅读与四阶段路线" style={{padding: "12px", borderBottom: "1px solid var(--line, #ddd)"}}>
    <p role="status">{({not_started:"尚未开始",active:"进行中",paused:"已暂放",ended:"本次片段已结束，仍有待核查内容",completed:"本次目标已完成",stale:"材料已换版，需要重新核查"} as Record<string,string>)[plan.status]}</p>
    <label>阅读深度 <select aria-label="阅读深度" disabled={busy} value={plan.depth} onChange={e => void act("start", {depth:e.target.value})}>
      <option value="skim">速览：决定是否继续</option><option value="understand">理解：机制、证据与回忆</option><option value="reconstruct">研读：推导、重建或最小检验</option>
    </select></label>
    <nav aria-label="可跳转的阅读阶段" style={{display:"flex", flexWrap:"wrap", gap:6, marginBlock:10}}>
      {plan.phases.map((p:any) => <button key={p.id} disabled={busy} aria-current={plan.current_phase===p.id ? "step" : undefined} onClick={() => void act("navigate", {phase:p.id})}>{p.label}</button>)}
    </nav>
    <p>{plan.pending_question || plan.phases.find((p:any)=>p.id===plan.current_phase)?.tasks[plan.current_task] || "选择一个当前值得核查的问题。"}</p>
    <p><small>阶段可跳转或暂放；覆盖记录不代表独立掌握。</small></p>
    <div style={{display:"flex", flexWrap:"wrap", gap:6}}>
      <button disabled={busy} onClick={() => void act(["paused","ended","completed"].includes(plan.status) ? "resume" : "pause")}>{["paused","ended","completed"].includes(plan.status) ? "继续本次阅读" : "暂放"}</button>
      <button disabled={busy} onClick={() => void act("finish", {reason:"用户选择结束本次阅读片段"})}>结束本次片段</button>
      {plan.bridge && <button disabled={busy} onClick={() => void act("return")}>回到补充知识前的问题</button>}
    </div>
    {error && <p role="alert">{error}</p>}
  </section>;
}

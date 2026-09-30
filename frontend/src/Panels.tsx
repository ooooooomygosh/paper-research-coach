import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Plus,
  RefreshCw,
  CheckCircle2,
  Link2,
  Download,
  Lightbulb,
} from "lucide-react";
import { api, put, type Row, location } from "./api";
const fields: Record<string, string> = {
  problem: "研究问题",
  unique_observation: "独特观察",
  prior_assumption: "前作假设",
  mechanism: "有效机制",
  information: "可用信息",
  objective: "目标与评价",
  dataset: "数据或系统",
  strongest_evidence: "最强证据与出处",
  failure_regime: "失效条件",
  project_relation: "与我的研究有关什么",
};
export function Lineage({
  seq = 0,
  paper,
  papers,
  refresh,
  report,
  onSelect,
}: {
  paper: Row;
  seq?: number;
  papers: Row[];
  refresh: () => void;
  report: (s: string) => void;
  onSelect: (id: string) => void;
}) {
  const [relations, setRelations] = useState<Row[]>([]),
    [comparison, setComparison] = useState<any>(paper.comparison),
    [comparisonBase, setComparisonBase] = useState(paper),
    [comparisonDirty, setComparisonDirty] = useState(false),
    [target, setTarget] = useState(""),
    [kind, setKind] = useState("prior"),
    [evidence, setEvidence] = useState(""),
    [url, setUrl] = useState(""),
    [verified, setVerified] = useState(false),
    [picked, setPicked] = useState<Row | null>(null);
  const comparisonRef = useRef(comparison);
  comparisonRef.current = comparison;
  const savingComparison = useRef(false);
  const loadSequence = useRef(0);
  async function load() {
    const request = ++loadSequence.current;
    const rows = await api("records/relation");
    if (request === loadSequence.current) setRelations(rows);
  }
  useEffect(() => {
    void load().catch((e) => report(String(e)));
    return () => {
      loadSequence.current++;
    };
  }, [paper.id, seq]);
  useEffect(() => {
    if (
      comparisonBase.id !== paper.id ||
      (!comparisonDirty && paper.revision > comparisonBase.revision)
    ) {
      setComparison(paper.comparison);
      setComparisonBase(paper);
      setComparisonDirty(false);
    }
  }, [paper.id, paper.revision, comparisonDirty]);
  const adjacent = relations.filter(
    (r) => r.paper_id === paper.id || r.target_id === paper.id,
  );
  const candidates = papers.filter(
    (p) => p.id !== paper.id && p.status !== "done",
  );
  const next =
    candidates.find((p) =>
      adjacent.some(
        (r) => (r.target_id === p.id || r.paper_id === p.id) && r.verified,
      ),
    ) || candidates[0];
  async function add() {
    try {
      await put("relation", {
        paper_id: paper.id,
        target_id: target,
        relation: kind,
        evidence,
        source_url: url,
        verified,
      });
      setEvidence("");
      await load();
      refresh();
    } catch (e) {
      report(String(e));
    }
  }
  return (
    <div className="workspace-view">
      <div className="view-heading">
        <span className="eyebrow">把一篇论文放回它的来路</span>
        <h2>研究脉络</h2>
        <p>关系需要依据。尚未核实的连接会用虚线显示。</p>
      </div>
      <div className="lineage-graph">
        <div className="graph-center">{paper.title}</div>
        {adjacent.map((r) => {
          const other = papers.find(
            (p) =>
              p.id === (r.paper_id === paper.id ? r.target_id : r.paper_id),
          );
          return (
            <button
              key={r.id}
              className={"graph-node " + (!r.verified ? "unverified" : "")}
              onClick={() => setPicked(r)}
            >
              <span>
                {r.relation} · {r.verified ? "已核实" : "待核实"}
              </span>
              {other?.title || "未知论文"}
              <Link2 size={13} />
            </button>
          );
        })}
        {!adjacent.length && (
          <p className="muted">
            从一篇最接近的前作开始，说明它与当前论文的关系。
          </p>
        )}
      </div>
      {picked && (
        <div className="callout">
          <b>{picked.relation} 的依据</b>
          <p className="preserve">{picked.evidence || "尚未记录依据"}</p>
          {/^https?:\/\//.test(picked.source_url) && (
            <a href={picked.source_url} target="_blank" rel="noreferrer">
              查看来源 ↗
            </a>
          )}
          <button className="text-button" onClick={() => setPicked(null)}>
            收起
          </button>
        </div>
      )}
      <details className="surface">
        <summary>连接一篇论文</summary>
        <div className="form-grid">
          <label>
            关联论文
            <select value={target} onChange={(e) => setTarget(e.target.value)}>
              <option value="">选择已导入论文</option>
              {papers
                .filter((p) => p.id !== paper.id)
                .map((p) => (
                  <option value={p.id} key={p.id}>
                    {p.title}
                  </option>
                ))}
            </select>
          </label>
          <label>
            关联论文与当前论文的关系
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="prior">前作：当前建立在关联论文之上</option>
              <option value="extends">扩展：当前扩展关联论文</option>
              <option value="alternative">替代路线</option>
              <option value="challenges">当前挑战关联论文</option>
              <option value="reproduces">当前复现关联论文</option>
            </select>
          </label>
          <label>
            依据
            <textarea
              value={evidence}
              onChange={(e) => setEvidence(e.target.value)}
              placeholder="具体机制、引文、图表或反例"
            />
          </label>
          <label>
            来源链接
            <input value={url} onChange={(e) => setUrl(e.target.value)} />
          </label>
        </div>
        <label className="check-label">
          <input
            type="checkbox"
            checked={verified}
            onChange={(e) => setVerified(e.target.checked)}
          />
          我已核实这条关系
        </label>
        <button
          className="primary"
          disabled={!target || !evidence.trim()}
          onClick={add}
        >
          保存关系
        </button>
      </details>
      {next && (
        <div className="next-paper">
          <div>
            <span className="eyebrow">下一篇候选</span>
            <h3>{next.title}</h3>
            <p>
              {adjacent.some(
                (r) =>
                  (r.target_id === next.id || r.paper_id === next.id) &&
                  r.verified,
              )
                ? "它与当前论文有已核实的关系，可用于比较假设和机制。"
                : "它在未完成的阅读队列中；请和宿主一起确认是否符合当前研究目标。"}
            </p>
          </div>
          <button onClick={() => onSelect(next.id)}>
            <ArrowRight size={18} />
          </button>
        </div>
      )}
      <div className="surface">
        <h3>统一比较记录</h3>
        <p className="muted small">
          用自己的话填写。证据字段写明图、表、命题或页码。
        </p>
        <div className="form-grid">
          {Object.entries(fields).map(([k, label]) => (
            <label key={k}>
              {label}
              <textarea
                value={comparison[k] || ""}
                onChange={(e) => {
                  setComparisonDirty(true);
                  setComparison({ ...comparison, [k]: e.target.value });
                }}
              />
            </label>
          ))}
        </div>
        {comparisonDirty && comparisonBase.revision !== paper.revision && (
          <div className="notice">
            其他地方已更新这篇论文。当前填写已保留，保存时会检查版本。
            <details>
              <summary>对照最新比较记录</summary>
              <pre>{JSON.stringify(paper.comparison, null, 2)}</pre>
            </details>
            <button
              onClick={() => {
                setComparison(paper.comparison);
                setComparisonBase(paper);
                setComparisonDirty(false);
              }}
            >
              放弃当前修改，载入最新记录
            </button>
          </div>
        )}
        <button
          className="primary"
          onClick={async () => {
            if (savingComparison.current) return;
            savingComparison.current = true;
            const snapshot = comparisonRef.current;
            try {
              const saved = await put("paper", {
                ...comparisonBase,
                comparison: snapshot,
              });
              setComparisonBase(saved);
              if (comparisonRef.current === snapshot) {
                setComparison(saved.comparison);
                setComparisonDirty(false);
              }
              refresh();
              report(
                comparisonRef.current === snapshot
                  ? "比较记录已保存"
                  : "上次提交已保存；新输入仍待保存",
              );
            } catch (e) {
              report(String(e));
            } finally {
              savingComparison.current = false;
            }
          }}
        >
          保存比较记录
        </button>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>论文</th>
              {Object.values(fields).map((f) => (
                <th key={f}>{f}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {papers.map((p) => (
              <tr key={p.id}>
                <th>{p.title}</th>
                {Object.keys(fields).map((f) => (
                  <td key={f}>{p.comparison[f] || "—"}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
const ideaFields: Record<string, string> = {
  title: "问题名称",
  observation: "从什么现象出发？",
  hypothesis: "可证伪的假设",
  alternative: "其他可能的解释",
  baseline: "最简单但有竞争力的基线",
  minimal_test: "最小区分实验或证明",
  negative_outcome: "什么结果会让我改变判断？",
  literature_question: "下一次检索只解决什么问题？",
};
export function Ideas({
  seq = 0,
  paper,
  report,
}: {
  paper: Row;
  seq?: number;
  report: (s: string) => void;
}) {
  const [ideas, setIdeas] = useState<Row[]>([]),
    [editing, setEditing] = useState<any>(null);
  const loadSequence = useRef(0);
  async function load() {
    const request = ++loadSequence.current;
    const rows = await api("records/idea?paper_id=" + paper.id);
    if (request === loadSequence.current) setIdeas(rows);
  }
  useEffect(() => {
    void load().catch((e) => report(String(e)));
    return () => {
      loadSequence.current++;
    };
  }, [paper.id, seq]);
  return (
    <div className="workspace-view">
      <div className="view-heading">
        <span className="eyebrow">让直觉变成能被推翻的问题</span>
        <h2>研究想法</h2>
        <p>从一个失败现象、矛盾结论或有效机制开始。</p>
        <button
          className="primary"
          onClick={() => setEditing({ paper_id: paper.id, status: "seed" })}
        >
          <Plus size={16} />
          记录一个切入口
        </button>
      </div>
      {editing && (
        <div className="surface">
          <div className="form-grid">
            {Object.entries(ideaFields).map(([key, label]) => (
              <label key={key}>
                {label}
                <textarea
                  value={editing[key] || ""}
                  onChange={(e) =>
                    setEditing({ ...editing, [key]: e.target.value })
                  }
                />
              </label>
            ))}
            <label>
              当前判断
              <select
                value={editing.status}
                onChange={(e) =>
                  setEditing({ ...editing, status: e.target.value })
                }
              >
                <option value="seed">萌芽</option>
                <option value="checking">查证中</option>
                <option value="testable">可检验</option>
                <option value="reframe">重新提问</option>
                <option value="killed">停止此假设</option>
              </select>
            </label>
          </div>
          <div className="button-row">
            <button
              className="primary"
              disabled={!editing.title?.trim()}
              onClick={async () => {
                try {
                  await put("idea", editing);
                  setEditing(null);
                  await load();
                } catch (e) {
                  report(String(e));
                }
              }}
            >
              保存研究问题
            </button>
            <button onClick={() => setEditing(null)}>取消</button>
          </div>
        </div>
      )}
      <div className="idea-grid">
        {ideas.map((i) => (
          <article className="surface idea-card" key={i.id}>
            <div className="note-meta">
              <Lightbulb size={18} />
              <span>
                {
                  (
                    {
                      seed: "萌芽",
                      checking: "查证中",
                      testable: "可检验",
                      reframe: "重新提问",
                      killed: "已停止",
                    } as any
                  )[i.status]
                }
              </span>
            </div>
            <h3>{i.title}</h3>
            <p className="preserve">
              {i.hypothesis || i.observation || "等待补充观察"}
            </p>
            <div className="mini-label">最小检验</div>
            <p className="preserve small">
              {i.minimal_test || "下一步：设计一个能区分解释的检验。"}
            </p>
            <button className="text-button" onClick={() => setEditing(i)}>
              展开与修改 <ArrowRight size={14} />
            </button>
          </article>
        ))}
      </div>
      {!ideas.length && !editing && (
        <div className="empty">
          “如果这个机制真在起作用，那么改变什么应该改变结果？”
        </div>
      )}
    </div>
  );
}
export function Reviews({
  seq = 0,
  paper,
  report,
  onLocate,
}: {
  paper: Row;
  seq?: number;
  report: (s: string) => void;
  onLocate: (a: any) => void;
}) {
  const [reviews, setReviews] = useState<Row[]>([]),
    [prompt, setPrompt] = useState(""),
    [intervals, setIntervals] = useState("1,3,7,14"),
    [answer, setAnswer] = useState(""),
    [help, setHelp] = useState("none"),
    [active, setActive] = useState<string | null>(null),
    [past, setPast] = useState<Row | null>(null);
  const loadSequence = useRef(0);
  async function load() {
    const request = ++loadSequence.current;
    const rows = await api("records/review?paper_id=" + paper.id);
    if (request === loadSequence.current) setReviews(rows);
  }
  useEffect(() => {
    void load().catch((e) => report(String(e)));
    return () => {
      loadSequence.current++;
    };
  }, [paper.id, seq]);
  async function submit(r: Row, success: boolean) {
    try {
      await api("review/" + r.id, {
        answer,
        assistance: help,
        success,
        expected_revision: r.revision,
      });
      setAnswer("");
      setActive(null);
      await load();
    } catch (e) {
      report(String(e));
    }
  }
  return (
    <div className="workspace-view">
      <div className="view-heading">
        <span className="eyebrow">先回忆，再回到证据</span>
        <h2>复习队列</h2>
        <p>这些问题来自已读内容。间隔可以调整，不发送系统通知。</p>
      </div>
      <details className="surface">
        <summary>加入一道提取练习</summary>
        <label>
          不看论文时，你希望能解释什么？
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="例如：作者的机制如何排除一个替代解释？"
          />
        </label>
        <label>
          复习间隔（天，逗号分隔）
          <input
            value={intervals}
            onChange={(e) => setIntervals(e.target.value)}
          />
        </label>
        <button
          className="primary"
          disabled={!prompt.trim()}
          onClick={async () => {
            try {
              await put("review", {
                paper_id: paper.id,
                prompt,
                intervals: intervals.split(",").map(Number),
              });
              setPrompt("");
              await load();
            } catch (e) {
              report(String(e));
            }
          }}
        >
          加入队列
        </button>
      </details>
      {[...reviews]
        .sort((a, b) => a.due_at.localeCompare(b.due_at))
        .map((r) => (
          <article className="surface" key={r.id}>
            <div className="note-meta">
              <span>
                {r.due_at <= new Date().toISOString()
                  ? "现在可以复习"
                  : "下次：" + new Date(r.due_at).toLocaleDateString()}
              </span>
              <span>{r.attempts.length} 次回忆</span>
            </div>
            <h3>{r.prompt}</h3>
            {active !== r.id ? (
              <div className="button-row">
                <button
                  onClick={() => {
                    setActive(r.id);
                    setAnswer("");
                    setHelp("none");
                  }}
                >
                  开始回忆
                </button>
                <button
                  className="text-button"
                  onClick={() => setPast(past?.id === r.id ? null : r)}
                >
                  查看以往回答
                </button>
                <label className="inline-label">
                  间隔
                  <input
                    aria-label="调整复习间隔"
                    defaultValue={r.intervals.join(",")}
                    onBlur={async (e) => {
                      const value = e.target.value.split(",").map(Number);
                      if (JSON.stringify(value) !== JSON.stringify(r.intervals))
                        try {
                          await put("review", { ...r, intervals: value });
                          await load();
                        } catch (err) {
                          report(String(err));
                        }
                    }}
                  />
                </label>
              </div>
            ) : (
              <>
                <textarea
                  aria-label="复习回答"
                  placeholder="先用自己的话解释，不必追求完整…"
                  value={answer}
                  onChange={(e) => setAnswer(e.target.value)}
                />
                <label>
                  这次用了多少帮助？
                  <select
                    value={help}
                    onChange={(e) => setHelp(e.target.value)}
                  >
                    <option value="none">独立完成</option>
                    <option value="hint">看了提示</option>
                    <option value="worked">看了完整解释</option>
                  </select>
                </label>
                <div className="button-row">
                  <button
                    className="primary"
                    disabled={!answer.trim()}
                    onClick={() => submit(r, true)}
                  >
                    能解释清楚
                  </button>
                  <button
                    disabled={!answer.trim()}
                    onClick={() => submit(r, false)}
                  >
                    还需要再读
                  </button>
                  {r.anchor && (
                    <button onClick={() => onLocate(r.anchor)}>回到证据</button>
                  )}
                </div>
              </>
            )}
            {past?.id === r.id &&
              r.attempts.map((a: any, i: number) => (
                <blockquote key={i}>
                  <span className="small">
                    {new Date(a.at).toLocaleString()} · {({none: "独立完成", hint: "看了提示", worked: "看了完整解释"} as Record<string, string>)[a.assistance] || "帮助程度待确认"}
                  </span>
                  <p className="preserve">{a.answer}</p>
                </blockquote>
              ))}
          </article>
        ))}
      {!reviews.length && (
        <div className="empty">先读出一个关键认识，再为它留一道复习题。</div>
      )}
    </div>
  );
}
export function Settings({
  state,
  refresh,
  report,
}: {
  state: any;
  refresh: () => void;
  report: (s: string) => void;
}) {
  const [collections, setCollections] = useState<any>(null),
    [selected, setSelected] = useState(state.sync.collection || ""),
    [busy, setBusy] = useState(false),
    [vaultPath, setVaultPath] = useState(state.vault?.root || "");
  async function perform(fn: () => Promise<any>) {
    setBusy(true);
    try {
      const result = await fn();
      refresh();
      return result;
    } catch (e) {
      report(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="workspace-view settings">
      <div className="view-heading">
        <span className="eyebrow">本机保存，按所选集合同步</span>
        <h2>Zotero 连接</h2>
        <p>需要 Zotero 10，并开启“设置 → 高级 → 允许本机其他应用通信”。</p>
      </div>
      <div className="surface">
        <h3>OneDrive / 本地文献目录</h3>
        <p>
          自动发现新增 PDF，并按文件内容关联
          Zotero。已有论文卡作为外部资料保留；新笔记以修订版本写入“06_PRC阅读记录”，可以直接编辑自己的原话文件。
        </p>
        <label>
          文献目录
          <input
            value={vaultPath}
            onChange={(e) => setVaultPath(e.target.value)}
            placeholder="文献阅读文件夹的完整路径"
          />
        </label>
        <div className="button-row">
          <button
            disabled={busy || !vaultPath}
            onClick={() =>
              perform(() => api("vault/configure", { root: vaultPath }))
            }
          >
            连接目录
          </button>
          <button
            disabled={busy || !state.vault?.enabled}
            onClick={() => perform(() => api("vault/scan", {}))}
          >
            立即检查新文件
          </button>
        </div>
        {state.vault?.enabled && (
          <p className="muted">
            {state.vault.collection
              ? "目录与 Zotero 已绑定。"
              : "仅目录已连接；选择 Zotero 集合后重新连接目录以完成绑定。"}{" "}
            已发现 {state.vault.pdf_count || 0} 份 PDF、
            {state.vault.card_count || 0} 张论文卡。服务运行时每 30 秒检查一次。
            {state.vault.message}
          </p>
        )}
        {(state.vault?.pending_metadata || []).length > 0 && (
          <details className="notice">
            <summary>这些论文的书目信息需要核实</summary>
            <p>
              可先在 Zotero 对 PDF
              使用“检索元数据”，再检查新文件。其他论文继续同步。
            </p>
            <ul>
              {state.vault.pending_metadata.map((p: any) => (
                <li key={p.paper_id}>{p.title}</li>
              ))}
            </ul>
          </details>
        )}
        {(state.vault_conflicts || []).map((c: any) => (
          <div className="notice" key={c.id}>
            <b>Markdown 与工作台同时修改</b>
            <p>{c.path}</p>
            <pre>{c.file_content}</pre>
            <div className="button-row">
              {[
                ["both", "保留为两条笔记"],
                ["file", "采用文件内容"],
                ["local", "采用工作台内容"],
              ].map(([choice, label]) => (
                <button
                  key={choice}
                  disabled={busy}
                  onClick={() =>
                    perform(() => api("vault/conflict/" + c.id, { choice }))
                  }
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="surface">
        <div className="sync-status">
          <span
            className={
              "status-dot " + (state.sync.state === "connected" ? "online" : "")
            }
          />
          <b>
            {state.sync.state === "connected"
              ? "已连接"
              : state.sync.state === "ready"
                ? "集合已选择"
                : "等待连接"}
          </b>
        </div>
        {state.sync.message && <p className="notice">{state.sync.message}</p>}
        <p className="muted">
          笔记先保存在本机。工作台运行时自动同步所选集合，关闭 Zotero
          后仍可阅读和记笔记。
        </p>
        <button
          disabled={busy}
          onClick={() =>
            perform(async () => setCollections(await api("zotero/collections")))
          }
        >
          <RefreshCw size={15} />
          读取我的集合
        </button>
        {collections && (
          <>
            <label>
              只同步这个集合
              <select
                value={selected}
                onChange={(e) => setSelected(e.target.value)}
              >
                <option value="">选择集合</option>
                {collections.collections.map((c: any) => (
                  <option key={c.key} value={c.key}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
            <button
              className="primary"
              disabled={!selected || busy}
              onClick={() =>
                perform(() =>
                  api("zotero/configure", {
                    server_id: collections.server_id,
                    collection: selected,
                    enabled: true,
                  }),
                )
              }
            >
              保存集合并开启同步
            </button>
          </>
        )}
        <div className="divider" />
        <h3>允许笔记写回 Zotero</h3>
        <p>
          点击后会出现 Zotero
          自身的授权弹窗。“始终允许”可用于持续同步；只选“允许”时授权仅供一次写入使用。授权信息保存在系统凭证库。
        </p>
        <div className="button-row">
          <button
            disabled={busy || !state.sync.server_id}
            onClick={() =>
              perform(async () => {
                const result = await api("zotero/authorize", {
                  server_id: state.sync.server_id,
                });
                report(
                  result.authorized
                    ? "Zotero 已授权" +
                        (result.session_only ? "（当前会话或一次写入）" : "")
                    : "Zotero 未授权；本地阅读继续可用",
                );
              })
            }
          >
            在 Zotero 中授权
          </button>
          <button
            disabled={busy || !state.sync.collection}
            onClick={() => perform(() => api("zotero/sync", {}))}
          >
            <RefreshCw size={15} />
            立即同步
          </button>
          {state.sync.collection && (
            <button
              disabled={busy}
              onClick={() =>
                perform(() =>
                  api("zotero/configure", {
                    server_id: state.sync.server_id,
                    collection: state.sync.collection,
                    enabled: !state.sync.enabled,
                  }),
                )
              }
            >
              {state.sync.enabled ? "暂停自动同步" : "开启自动同步"}
            </button>
          )}
        </div>
        {busy && (
          <p className="muted">
            正在处理；如已发起授权，请在 Zotero 弹窗中选择。
          </p>
        )}
        <p className="small muted">
          最近成功：
          {state.sync.last_success
            ? new Date(state.sync.last_success).toLocaleString()
            : "尚未同步"}
        </p>
      </div>
      {state.conflicts.length > 0 && (
        <>
          <h3>保留双方版本，等待你的决定</h3>
          {state.conflicts.map((c: any) => (
            <article className="surface" key={c.id}>
              <b>
                {(
                  {
                    "both-edited": "两边都修改过",
                    "remote-delete": "Zotero 中已删除",
                    "paper-remote-delete":
                      "Zotero 父条目已删除，本地论文和笔记仍保留",
                    "local-delete": "本地已归档，是否同步删除？",
                    "anchor-type-changed": "位置类型发生变化",
                  } as any
                )[c.reason] || c.reason}
              </b>
              <div className="conflict-columns">
                <div>
                  <h4>本地版本</h4>
                  <p className="preserve">
                    {c.local_data.content || c.local_data.title}
                  </p>
                  <button
                    disabled={busy}
                    onClick={() =>
                      perform(() =>
                        api("zotero/conflict/" + c.id, { choice: "local" }),
                      )
                    }
                  >
                    {c.reason === "paper-remote-delete"
                      ? "保留本地论文并断开同步"
                      : "采用本地版本"}
                  </button>
                </div>
                <div>
                  <h4>Zotero 版本</h4>
                  <p className="preserve">
                    {c.remote_data.deleted
                      ? "已删除"
                      : c.remote_data.annotationComment ||
                        c.remote_data.annotationText ||
                        c.remote_data.note ||
                        "未获取内容"}
                  </p>
                  <button
                    disabled={busy}
                    onClick={() =>
                      perform(() =>
                        api("zotero/conflict/" + c.id, { choice: "remote" }),
                      )
                    }
                  >
                    {c.reason === "paper-remote-delete"
                      ? "归档本地论文，保留文件和笔记"
                      : "采用 Zotero 版本"}
                  </button>
                </div>
              </div>
              <p className="small muted">
                双方版本已记录在冲突记录与笔记修订历史中。不会删除原始论文。
              </p>
            </article>
          ))}
        </>
      )}
      <div className="surface">
        <h3>你的内容在哪里？</h3>
        <p>
          笔记、对话、研究想法与复习记录保存在本机；原始 PDF 保持只读。
          开启同步后，笔记写入所选 Zotero 集合，阅读记录写入已连接目录的
          “06_PRC阅读记录”。发送教练消息时，当前论文材料通过本机 CLI
          发给其配置的模型服务；登录信息由 CLI 管理。导出是独立副本。
        </p>
      </div>
    </div>
  );
}
export function Exports({
  paper,
  report,
}: {
  paper: Row;
  report: (s: string) => void;
}) {
  const [result, setResult] = useState<any>(null);
  return (
    <div className="workspace-view">
      <div className="view-heading">
        <span className="eyebrow">把积累带到下一次思考</span>
        <h2>导出与分享</h2>
        <p>导出内容由当前笔记生成。未核实的内容会保留状态，不补写事实。</p>
      </div>
      <div className="export-grid">
        {[
          ["paper", "论文卡", "贡献、比较记录、原话与阅读断点"],
          ["ideas", "研究问题卡", "假设、替代解释与最小检验"],
          ["talk", "汇报提纲", "面向听众的五分钟讲述结构"],
          ["comparison", "比较表 CSV", "所有论文使用同一组比较维度"],
          ["pdf", "独立批注 PDF", "仅把当前版本已核实的位置写入副本"],
        ].map(([kind, title, detail]) => (
          <button
            className="surface export-card"
            key={kind}
            onClick={async () => {
              try {
                setResult(await api("export", { kind, paper_id: paper.id }));
              } catch (e) {
                report(String(e));
              }
            }}
          >
            <Download size={22} />
            <h3>{title}</h3>
            <p>{detail}</p>
          </button>
        ))}
      </div>
      {result && (
        <div className="callout">
          <CheckCircle2 size={18} /> 导出已生成。{" "}
          <a href={result.download} download>
            下载文件
          </a>
          {result.unplaced_note_ids.length > 0 && (
            <p>
              {result.unplaced_note_ids.length} 条笔记尚未核实位置，未写入
              PDF，可在论文卡中查看。
            </p>
          )}
        </div>
      )}
    </div>
  );
}

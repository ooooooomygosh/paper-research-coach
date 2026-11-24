import { useEffect, useMemo, useRef, useState } from "react";
import { api, id, type Row } from "./api";
import { ALL_TOPICS, filterPapers, papersInTopic } from "./library-search";
import TopicPicker, { type TopicFilter } from "./TopicPicker";

export function hasTranslation(job: any): boolean {
  return Boolean(
    job &&
    job.current !== false &&
    (job.pdf_ready ?? job.state === "completed"),
  );
}

export function TranslationBadge({ job }: { job: any }) {
  if (!job || job.current === false) return null;
  const ready = hasTranslation(job);
  const text = ready
    ? "双语"
    : job.state === "running"
      ? "翻译中"
      : job.state === "queued"
        ? "待翻译"
        : "翻译待继续";
  return (
    <span
      className={"translation-badge " + (ready ? "ready" : "pending")}
      title={ready ? "中文与双语 PDF 已可阅读" : job.message || text}
    >
      {text}
    </span>
  );
}

export default function TranslationLibrary({
  papers,
  topicFilter,
  onUpdate,
  onRead,
}: {
  papers: Row[];
  topicFilter?: TopicFilter;
  onUpdate?: () => void;
  onRead?: (paperId: string) => void;
}) {
  const [profile, setProfile] = useState<any>(null);
  const [models, setModels] = useState<any[]>([]);
  const [overview, setOverview] = useState<any>({ data: [], papers: {} });
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const mounted = useRef(true);

  async function reload() {
    const jobs = await api("translation/jobs");
    if (mounted.current) setOverview(jobs);
  }
  useEffect(() => {
    mounted.current = true;
    let loading = false;
    async function poll() {
      if (loading) return;
      loading = true;
      try {
        await reload();
      } catch (e) {
        if (mounted.current) setError(String(e));
      } finally {
        loading = false;
      }
    }
    Promise.all([api("translation/settings"), api("coach/status")])
      .then(([p, s]) => {
        if (mounted.current) {
          setProfile(p);
          setModels(s.models || []);
        }
      })
      .catch((e) => {
        if (mounted.current) setError(String(e));
      });
    void poll();
    const timer = setInterval(() => void poll(), 4000);
    return () => {
      mounted.current = false;
      clearInterval(timer);
    };
  }, []);

  async function save(next: any) {
    setSaving(true);
    setError("");
    try {
      const saved = await api("translation/settings", {
        model: next.model,
        effort: next.effort,
        lang_in: next.lang_in,
        lang_out: next.lang_out,
        paper_concurrency: next.paper_concurrency ?? 2,
        request_concurrency: next.request_concurrency ?? 4,
      });
      setProfile({ ...next, ...saved });
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }
  const topic = topicFilter?.value ?? ALL_TOPICS;
  const topics = topicFilter?.topics;
  const candidates = useMemo(
    () => filterPapers(papersInTopic(papers, topics, topic), search),
    [papers, topics, topic, search],
  );
  const visible = candidates.filter((p) => {
    const job = overview.papers[p.id];
    return filter === "all" ||
      (filter === "ready" ? hasTranslation(job) : !hasTranslation(job));
  });
  const eligible = visible.filter(
    (p) =>
      p.source_version &&
      p.source_path &&
      !hasTranslation(overview.papers[p.id]) &&
      !["queued", "running"].includes(overview.papers[p.id]?.state),
  );
  const picked = papers.filter((p) => selected.has(p.id));
  const hiddenCount = picked.length - visible.filter((p) => selected.has(p.id)).length;
  function choose(paperId: string) {
    setSelected((previous) => {
      const next = new Set(previous);
      next.has(paperId) ? next.delete(paperId) : next.add(paperId);
      return next;
    });
  }
  async function start() {
    if (!picked.length) return;
    setBusy(true);
    setError("");
    setNotice("");
    const key =
      "prc-translation-batch:" +
      picked
        .map((p) => p.id + ":" + p.source_version)
        .sort()
        .join("|");
    try {
      const operationId = localStorage.getItem(key) || id();
      localStorage.setItem(key, operationId);
      const response = await api("translation/batch", {
        operation_id: operationId,
        papers: picked.map((p) => ({
          paper_id: p.id,
          source_version: p.source_version,
        })),
      });
      localStorage.removeItem(key);
      const failures = response.data.filter((r: any) => r.outcome === "error");
      const added = response.data.filter(
        (r: any) => r.outcome === "queued",
      ).length;
      const existing = response.data.filter(
        (r: any) => r.outcome === "existing",
      ).length;
      setNotice(
        `已加入 ${added} 篇${existing ? `，${existing} 篇已有译文或正在处理` : ""}。可以切换页面或关闭面板；完全退出 Harness 会保存进度，重启后继续。`,
      );
      setSelected(new Set(failures.map((r: any) => r.paper_id)));
      if (failures.length)
        setError(
          failures
            .map(
              (r: any) =>
                `${papers.find((p) => p.id === r.paper_id)?.title || "论文"}：${r.message}`,
            )
            .join("；"),
        );
      await reload();
      onUpdate?.();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  async function action(job: any, kind: "stop" | "retry") {
    setBusy(true);
    setError("");
    try {
      await api(`translation/jobs/${job.id}/${kind}`, {});
      await reload();
      onUpdate?.();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  const active = overview.data.filter(
    (j: any) => ["queued", "running"].includes(j.state) && j.current,
  );
  const model = models.find((m) => m.model === profile?.model);
  const activeByPaper = Object.fromEntries(
    [...active].reverse().map((j: any) => [j.paper_id, j]),
  );
  return (
    <section className="surface translation-library" aria-label="后台批量翻译">
      <h3>后台批量翻译</h3>
      {profile && (
        <details className="translation-advanced">
          <summary>批量翻译高级设置</summary>
          <div className="form-grid translation-profile">
          <label>
            翻译模型
            <select
              aria-label="批量翻译模型"
              disabled={saving}
              value={profile.model}
              onChange={(e) => {
                const chosen = models.find((m) => m.model === e.target.value);
                void save({
                  ...profile,
                  model: e.target.value,
                  effort: chosen?.supportedReasoningEfforts?.some(
                    (r: any) => r.reasoningEffort === "low",
                  )
                    ? "low"
                    : chosen?.defaultReasoningEffort || "low",
                });
              }}
            >
              {!model && (
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
            思考深度
            <select
              aria-label="批量翻译思考深度"
              disabled={saving}
              value={profile.effort}
              onChange={(e) =>
                void save({ ...profile, effort: e.target.value })
              }
            >
              {(
                model?.supportedReasoningEfforts || [{ reasoningEffort: "low" }]
              ).map((r: any) => (
                <option key={r.reasoningEffort} value={r.reasoningEffort}>
                  {r.reasoningEffort}
                </option>
              ))}
            </select>
          </label>
          <label>
            同时翻译论文
            <select
              aria-label="同时翻译论文"
              disabled={saving}
              value={profile.paper_concurrency ?? 2}
              onChange={(e) =>
                void save({
                  ...profile,
                  paper_concurrency: Number(e.target.value),
                })
              }
            >
              {[1, 2, 3, 4].map((n) => (
                <option key={n} value={n}>
                  {n} 篇
                </option>
              ))}
            </select>
          </label>
          <label>
            模型请求并发
            <select
              aria-label="模型请求并发"
              disabled={saving}
              value={profile.request_concurrency ?? 4}
              onChange={(e) =>
                void save({
                  ...profile,
                  request_concurrency: Number(e.target.value),
                })
              }
            >
              {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => (
                <option key={n} value={n}>
                  {n} 个
                </option>
              ))}
            </select>
          </label>
          </div>
          <p className="muted small">请求并发由所有论文共享；已有任务保持启动时的模型，并发设置立即生效。</p>
        </details>
      )}
      {!profile?.component?.ready && profile && (
        <p role="status">请先安装 BabelDOC 翻译组件。</p>
      )}
      <div className="translation-library-controls">
        {topicFilter && topicFilter.topics.options.length > 1 && (
          <TopicPicker filter={topicFilter} label="批量翻译主题" />
        )}
        <input
          aria-label="搜索待翻译论文"
          placeholder={topic ? "在当前主题内搜索" : "搜索标题、作者、年份或 DOI…"}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          aria-label="筛选译文状态"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          <option value="all">全部状态</option>
          <option value="missing">还没有双语版</option>
          <option value="ready">双语已可读</option>
        </select>
        <button
          disabled={busy || !eligible.length}
          onClick={() => {
            setSelected(
              (previous) =>
                new Set([...previous, ...eligible.map((p) => p.id)]),
            );
          }}
        >
          勾选当前结果
        </button>
        <button
          disabled={busy || !picked.length}
          onClick={() => setSelected(new Set())}
        >
          清空勾选
        </button>
      </div>
      <div className="translation-library-list">
        {visible.map((p) => {
          const job = overview.papers[p.id];
          const task = activeByPaper[p.id] || job;
          const ready = hasTranslation(job);
          const running = ["queued", "running"].includes(task?.state);
          return (
            <div className="translation-library-row" key={p.id}>
              <label className="translation-paper-choice">
                <input
                  type="checkbox"
                  aria-label={`翻译 ${p.title}`}
                  checked={selected.has(p.id)}
                  disabled={
                    busy ||
                    ready ||
                    running ||
                    !p.source_version ||
                    !p.source_path
                  }
                  onChange={() => choose(p.id)}
                />
                <span>
                  <strong>{p.title}</strong>
                  <small>
                    {p.authors || p.year || ""}
                    {!p.source_path && " · 没有本机 PDF"}
                  </small>
                </span>
              </label>
              <div className="translation-paper-status">
                <TranslationBadge job={job} />
                {running && (
                  <small>
                    {task.stage}
                    {task.state === "running" &&
                      ` · ${Math.round(task.progress || 0)}%`}
                  </small>
                )}
                {job?.message && <small>{job.message}</small>}
                {ready && onRead && (
                  <button onClick={() => onRead(p.id)}>阅读双语</button>
                )}
                {running ? (
                  <button
                    disabled={busy}
                    onClick={() => void action(task, "stop")}
                  >
                    停止
                  </button>
                ) : (
                  job &&
                  ["failed", "cancelled", "interrupted"].includes(
                    job.state,
                  ) && (
                    <button
                      disabled={busy}
                      onClick={() => void action(job, "retry")}
                    >
                      继续翻译
                    </button>
                  )
                )}
              </div>
            </div>
          );
        })}
        {!visible.length && <p className="muted" role="status">当前筛选结果为 0 篇。</p>}
      </div>
      <div className="translation-batch-footer">
        <span role="status">
          {visible.length} 篇结果 · 已勾选 {picked.length} 篇
          {hiddenCount > 0 && `（含其他筛选结果中的 ${hiddenCount} 篇）`}
          {" · 后台 "}{active.length} 篇
        </span>
        <button
          className="primary"
          disabled={
            busy ||
            saving ||
            !picked.length ||
            !profile?.component?.ready ||
            !model
          }
          onClick={() => void start()}
        >
          {busy ? "正在处理…" : "加入后台翻译"}
        </button>
      </div>
      {notice && <p role="status">{notice}</p>}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}

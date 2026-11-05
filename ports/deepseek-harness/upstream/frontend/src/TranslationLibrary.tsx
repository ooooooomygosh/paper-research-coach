import { useEffect, useRef, useState } from "react";
import { api, id, type Row } from "./api";

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
  onUpdate,
  onRead,
}: {
  papers: Row[];
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
  const operation = useRef("");
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
  const visible = papers.filter((p) => {
    const job = overview.papers[p.id];
    const matches = [p.title, p.authors, p.year]
      .join(" ")
      .toLowerCase()
      .includes(search.toLowerCase().trim());
    return (
      matches &&
      (filter === "all" ||
        (filter === "ready" ? hasTranslation(job) : !hasTranslation(job)))
    );
  });
  const eligible = visible.filter(
    (p) =>
      p.source_version &&
      p.source_path &&
      !hasTranslation(overview.papers[p.id]) &&
      !["queued", "running"].includes(overview.papers[p.id]?.state),
  );
  function choose(paperId: string) {
    setSelected((previous) => {
      const next = new Set(previous);
      next.has(paperId) ? next.delete(paperId) : next.add(paperId);
      return next;
    });
    operation.current = "";
  }
  async function start() {
    setBusy(true);
    setError("");
    setNotice("");
    const picked = papers.filter((p) => selected.has(p.id));
    const key =
      "prc-translation-batch:" +
      picked
        .map((p) => p.id + ":" + p.source_version)
        .sort()
        .join("|");
    operation.current = localStorage.getItem(key) || id();
    localStorage.setItem(key, operation.current);
    try {
      const response = await api("translation/batch", {
        operation_id: operation.current,
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
        `已加入 ${added} 篇${existing ? `，${existing} 篇已有译文或正在处理` : ""}。可以关闭网页，后台会继续翻译。`,
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
      <p>
        提前准备想读的论文。选中后加入后台队列，双语 PDF
        生成后即可阅读，句子对应继续在后台完成。
      </p>
      {profile && (
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
      )}
      <p className="muted small">
        请求并发由所有论文共享。已有任务保持启动时的模型；并发设置立即生效。关闭网页不影响任务，电脑和本机工作台需保持运行。
      </p>
      {!profile?.component?.ready && profile && (
        <p role="status">请先安装 BabelDOC 翻译组件。</p>
      )}
      <div className="translation-library-controls">
        <input
          aria-label="搜索待翻译论文"
          placeholder="搜索标题、作者或年份…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          aria-label="筛选译文状态"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          <option value="all">全部论文</option>
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
            operation.current = "";
          }}
        >
          勾选搜索结果
        </button>
        <button
          disabled={busy || !selected.size}
          onClick={() => {
            setSelected(new Set());
            operation.current = "";
          }}
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
        {!visible.length && <p className="muted">没有匹配的论文。</p>}
      </div>
      <div className="translation-batch-footer">
        <span>
          已勾选 {selected.size} 篇 · 后台 {active.length} 篇
        </span>
        <button
          className="primary"
          disabled={
            busy ||
            saving ||
            !selected.size ||
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

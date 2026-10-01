import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  BookOpen,
  Network,
  Lightbulb,
  RotateCcw,
  Download,
  Settings as SettingsIcon,
  Plus,
  ArrowRight,
  Play,
  Pause,
  Search,
  X,
  ChevronDown,
  MessageCircle,
  PanelLeftClose,
  PanelLeftOpen,
  MoreHorizontal,
  Maximize2,
  Minimize2,
} from "lucide-react";
import { api, ApiError, put, anchorFor, anchorQuote, id, type Row } from "./api";
import { readLaunchInput } from "./launch";
import { filterPapers } from "./library-search";
import Welcome from "./Welcome";
import Dialog from "./Dialog";
import { ImportModal, PaperEditor } from "./PaperDialogs";
import PdfReader from "./PdfReader";
import Notes from "./Notes";
import CoachPanel from "./Coach";
import { Lineage, Ideas, Reviews, Settings, Exports } from "./Panels";
import "./style.css";
import "./quiet-reading.css";
import "./workbench-polish.css";
import {
  TranslationTools,
  TranslationPopover,
  type PdfView,
} from "./ReadingTools";
import { hasTranslation, TranslationBadge } from "./TranslationLibrary";
const stages: Record<string, string> = {
  orient: "确定当前需要",
  insight: "抓住独特贡献",
  model: "理解问题设定",
  method: "拆解核心机制",
  evidence: "检验证据",
  synthesis: "形成自己的解释",
  transfer: "连接研究问题",
  recall: "回忆与复习",
  talk: "准备汇报",
};
const nav = [
  ["read", "继续阅读", BookOpen],
  ["lineage", "研究脉络", Network],
  ["ideas", "研究想法", Lightbulb],
  ["review", "复习队列", RotateCcw],
  ["export", "导出", Download],
] as const;
export function App() {
  const [ready, setReady] = useState(false),
    [state, setState] = useState<any>({ papers: [], sync: {}, conflicts: [] }),
    [selected, setSelected] = useState(
      localStorage.getItem("prc-selected") || "",
    ),
    [context, setContext] = useState<any>(null),
    [tab, setTab] = useState("read"),
    [page, setPage] = useState(0),
    [anchor, setAnchor] = useState<any>(null),
    [focusAnchor, setFocusAnchor] = useState<any>(null),
    [error, setError] = useState(""),
    [importing, setImporting] = useState(false),
    [search, setSearch] = useState(""),
    [taskEditor, setTaskEditor] = useState<any>(null),
    [login, setLogin] = useState(""),
    [paperEditor, setPaperEditor] = useState<any>(null);
  const [readingPane, setReadingPane] = useState("coach");
  const [sidebarHidden, setSidebarHidden] = useState(
    () => localStorage.getItem("prc-sidebar-hidden") !== "false",
  );
  const [immersive, setImmersive] = useState(false);
  const [toolsOpen, setToolsOpen] = useState(false);
  const [toolsTab, setToolsTab] = useState("translate");
  const [syncBusy, setSyncBusy] = useState(false);
  const [syncError, setSyncError] = useState("");
  const [coachTools, setCoachTools] = useState<HTMLElement | null>(null);
  const [pdfTools, setPdfTools] = useState<HTMLElement | null>(null);
  const [split, setSplit] = useState(() =>
    Math.max(
      0.45,
      Math.min(0.8, Number(localStorage.getItem("prc-pane-ratio")) || 0.7),
    ),
  );
  const [translationJob, setTranslationJob] = useState<any>(null);
  const [translationPdfJob, setTranslationPdfJob] = useState<any>(null);
  const [translationIndex, setTranslationIndex] = useState<any>({});
  const translationChoice = useRef("");
  const [exportingPdf, setExportingPdf] = useState(false);
  const [newNoteRequest, setNewNoteRequest] = useState<{ id: string; anchor: any } | null>(null);
  const translatedRead = useRef("");
  const [pdfView, setPdfView] = useState<PdfView>("original");
  const [selection, setSelection] = useState<any>(null);
  const [markedSelection, setMarkedSelection] = useState("");
  const layout = useRef<HTMLDivElement>(null);
  const toolsTrigger = useRef<HTMLElement | null>(null);
  function closeTools() {
    setToolsOpen(false);
    toolsTrigger.current?.focus();
  }
  function openTools(section = "translate") {
    toolsTrigger.current = document.activeElement as HTMLElement;
    setToolsTab(section);
    setToolsOpen(true);
  }
  async function refreshSync() {
    setSyncBusy(true);
    setSyncError("");
    try {
      const result = await api("sync/refresh", {});
      setSyncError(
        Object.values(result)
          .filter((s: any) => s.state === "attention")
          .map((s: any) => s.message)
          .join("；"),
      );
      await refresh();
    } catch (e) {
      setSyncError(String(e));
    } finally {
      setSyncBusy(false);
    }
  }
  function ratio(value: number) {
    const next = Math.max(0.45, Math.min(0.8, value));
    setSplit(next);
    localStorage.setItem("prc-pane-ratio", String(next));
  }
  function immersiveToggle() {
    setImmersive((v) => !v);
    setToolsOpen(false);
  }
  useEffect(() => {
    function keyboard(e: KeyboardEvent) {
      if (e.defaultPrevented || document.querySelector("dialog[open]")) return;
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === "Enter") {
        e.preventDefault();
        immersiveToggle();
      }
      if (e.key === "Escape") {
        if (toolsOpen) {
          e.preventDefault();
          closeTools();
        } else if (selection) {
          e.preventDefault();
          setSelection(null);
        } else if (immersive) {
          e.preventDefault();
          setImmersive(false);
        } else if (!sidebarHidden) setSidebarHidden(true);
      }
    }
    document.addEventListener("keydown", keyboard);
    return () => document.removeEventListener("keydown", keyboard);
  }, [immersive, toolsOpen, selection, sidebarHidden]);
  const [launchConversation, setLaunchConversation] = useState("");
  const launchRef = useRef("");
  const selectedRef = useRef(selected),
    pageTimer = useRef<any>(null);
  selectedRef.current = selected;
  function report(s: string) {
    setError(s);
  }
  async function refresh() {
    const s = await api("state");
    setState(s);
    const chosen = s.papers.some((p: Row) => p.id === selectedRef.current)
      ? selectedRef.current
      : s.papers[0]?.id;
    if (chosen) {
      if (selectedRef.current !== chosen) {
        selectedRef.current = chosen;
        setSelected(chosen);
      }
      const c = await api("context/" + chosen);
      if (chosen === selectedRef.current) setContext(c);
    } else {
      selectedRef.current = "";
      setSelected("");
      setContext(null);
      localStorage.removeItem("prc-selected");
    }
  }
  async function start(token?: string) {
    try {
      if (token) await api("login", { token });
      await refresh();
      setError("");
      setReady(true);
    } catch (e) {
      setError(
        e instanceof ApiError && e.status === 401
          ? token
            ? "启动链接已失效，请从本机启动器重新打开。"
            : ""
          : e instanceof Error
            ? e.message
            : String(e),
      );
    }
  }
  function connectFromInput() {
    try {
      const link = readLaunchInput(login, location.origin);
      if (link.paper) {
        selectedRef.current = link.paper;
        setSelected(link.paper);
        setContext(null);
        launchRef.current = link.conversation;
        setLaunchConversation(link.conversation);
      }
      setLogin("");
      void start(link.token);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }
  useEffect(() => {
    function openLaunch() {
      const t = new URLSearchParams(location.hash.slice(1)).get("token");
      const launchPaper = new URLSearchParams(location.hash.slice(1)).get(
        "paper",
      );
      if (launchPaper) {
        selectedRef.current = launchPaper;
        setSelected(launchPaper);
        setContext(null);
        launchRef.current =
          new URLSearchParams(location.hash.slice(1)).get("conversation") || "";
        setLaunchConversation(launchRef.current);
        setTab("read");
        setReadingPane("coach");
      }
      if (t) history.replaceState(null, "", location.pathname);
      void start(t || undefined);
    }
    openLaunch();
    window.addEventListener("hashchange", openLaunch);
    return () => window.removeEventListener("hashchange", openLaunch);
  }, []);
  useEffect(() => {
    if (!ready || !selected) return;
    let disposed = false;
    api("context/" + selected)
      .then((c) => {
        if (!disposed) {
          setContext(c);
          const savedPage = Number(
            localStorage.getItem(
              "prc-page-" + c.paper.id + ":" + c.paper.source_version,
            ),
          );
          setPage(
            Number.isInteger(savedPage) &&
              localStorage.getItem(
                "prc-page-" + c.paper.id + ":" + c.paper.source_version,
              ) !== null &&
              savedPage >= 0 &&
              savedPage < c.paper.page_count
              ? savedPage
              : c.session[0]?.cursor?.status === "stale"
                ? 0
                : c.session[0]?.cursor?.page_index || 0,
          );
          setAnchor(null);
          setFocusAnchor(null);
        }
      })
      .catch((e) => report(String(e)));
    localStorage.setItem("prc-selected", selected);
    void api("coach/active", { paper_id: selected }).catch(() => {});
    return () => {
      disposed = true;
      clearTimeout(pageTimer.current);
    };
  }, [selected, ready]);
  useEffect(() => {
    if (!ready) return;
    const events = new EventSource("/api/events");
    let timer: any;
    events.onmessage = () => {
      clearTimeout(timer);
      timer = setTimeout(
        () => void refresh().catch((e) => report(String(e))),
        150,
      );
    };
    const status = setInterval(() => void refresh().catch(() => {}), 12000);
    return () => {
      events.close();
      clearTimeout(timer);
      clearInterval(status);
    };
  }, [ready]);
  const paper = context?.paper,
    session = context?.session?.[0];
  async function reloadTranslation() {
    const pid = paper?.id,
      version = paper?.source_version;
    try {
      const result = await api("translation/jobs");
      setTranslationIndex(result.papers || {});
      if (!pid) return;
      if (
        selectedRef.current !== pid ||
        sourceRef.current?.source_version !== version
      )
        return;
      const current = result.data.find(
        (j: any) =>
          j.paper_id === pid &&
          j.source_version === version &&
          j.current !== false,
      );
      setTranslationJob(current || null);
      const readable = result.data.find((j: any) => j.id === translationChoice.current && j.paper_id === pid && j.current && hasTranslation(j)) || result.papers?.[pid];
      setTranslationPdfJob(hasTranslation(readable) ? readable : null);
      if (!hasTranslation(readable)) setPdfView("original");
      else if (translatedRead.current === pid) {
        setPdfView("dual");
        translatedRead.current = "";
      }
    } catch {
      /* Translation is optional; reading stays available. */
    }
  }
  useEffect(() => {
    setTranslationJob(null);
    translationChoice.current = "";
    setTranslationPdfJob(null);
    setPdfView("original");
    setSelection(null);
    if (!ready) return;
    void reloadTranslation();
    const poll = setInterval(() => void reloadTranslation(), 4000);
    return () => clearInterval(poll);
  }, [ready, paper?.id, paper?.source_version]);
  const sourceRef = useRef<any>(null);
  useEffect(() => {
    if (!paper) return;
    if (
      sourceRef.current?.id === paper.id &&
      sourceRef.current.source_version !== paper.source_version
    ) {
      clearTimeout(pageTimer.current);
      setPage(0);
      setAnchor(null);
      setFocusAnchor(null);
    }
    sourceRef.current = { id: paper.id, source_version: paper.source_version };
  }, [paper?.id, paper?.source_version]);
  function select(id: string) {
    launchRef.current = "";
    setLaunchConversation("");
    setContext(null);
    setSelected(id);
    selectedRef.current = id;
    setTab("read");
    setSidebarHidden(true);
    setTaskEditor(null);
  }
  function movePage(n: number) {
    setSelection(null);
    if (paper)
      localStorage.setItem(
        "prc-page-" + paper.id + ":" + paper.source_version + (pdfView === "original" ? "" : ":" + translationPdfJob?.id + ":" + pdfView),
        String(n),
      );
    setPage(n);
    setFocusAnchor(null);
    clearTimeout(pageTimer.current);
    const pid = selectedRef.current;
    if (pdfView !== "original") return;
    pageTimer.current = setTimeout(async () => {
      try {
        const c = await api("context/" + pid);
        const s = c.session[0];
        await put("session", { ...s, cursor: anchorFor(c.paper, n) });
        await refresh();
      } catch (e) {
        report(String(e));
      }
    }, 600);
  }
  async function locate(a: any) {
    if (a.status === "stale" || a.source_version !== paper.source_version) {
      report("这条笔记属于旧版本。原话仍在，请重新核实位置。");
      return;
    }
    if (a.rendition) {
      try {
        const r = a.rendition;
        const job = await api("translation/jobs/" + r.job_id);
        if (job.paper_id !== paper.id || !job.current || job.documents?.[r.view]?.document_version !== r.document_version) {
          report("这条批注对应的译本已改变或不可用，笔记仍然保留。");
          return;
        }
        translationChoice.current = job.id;
        setTranslationPdfJob(job);
        setPdfView(r.view);
        setTab("read");
        setPage(r.page_index);
        setSelection(null);
        setFocusAnchor(a);
        setToolsOpen(false);
      } catch (e) { report(String(e)); }
      return;
    }
    if (a.page_index === null) {
      report("这条笔记尚未定位到具体页面。");
      return;
    }
    setTab("read");
    setPdfView("original");
    movePage(a.page_index);
    setFocusAnchor(a);
  }
  async function exportCurrentPdf() {
    if (!paper || exportingPdf) return;
    setExportingPdf(true);
    try {
      const document = translationPdfJob?.documents?.[pdfView];
      const rendition = pdfView === "original" ? undefined : {
        job_id: translationPdfJob.id, view: pdfView, document_version: document.document_version, page_index: 0,
      };
      const result = await api("export", { kind: "pdf", paper_id: paper.id, rendition });
      const link = window.document.createElement("a");
      link.href = result.download; link.download = ""; link.click();
      if (result.unplaced_note_ids.length) report("已导出当前 PDF；其他版本或未定位的笔记保留在笔记库。");
    } catch (e) { report(String(e)); } finally { setExportingPdf(false); }
  }
  async function pause() {
    try {
      const c = await api("context/" + selected);
      await put("paper", {
        ...c.paper,
        status: c.paper.status === "paused" ? "reading" : "paused",
      });
      await put("session", {
        ...c.session[0],
        cursor: anchorFor(c.paper, page),
      });
      await refresh();
      report(
        c.paper.status === "paused"
          ? "已恢复阅读"
          : "已保存当前位置与下一步，随时可以接着读",
      );
    } catch (e) {
      report(String(e));
    }
  }
  const visiblePapers = filterPapers(state.papers, search);
  if (!ready)
    return (
      <main className="login">
        <div className="brand-mark">
          <BookOpen />
        </div>
        <h1>Paper Research Coach</h1>
        <p>这个浏览器还没有连接你的本机工作台。</p>
        <p className="muted">
          双击电脑上的“打开论文工作台”启动文件，会自动完成连接。 也可以在 Codex
          中说：“打开我的论文阅读工作台”。
        </p>
        <p className="small muted">已经安装？在终端运行 <code>prc open</code>，请勿分享带登录信息的启动链接。</p>
        <button className="primary" onClick={() => void start()}>
          已从启动器打开，重新检查连接
        </button>
        <details className="login-link">
          <summary>我已有启动链接</summary>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              connectFromInput();
            }}
          >
            <label>
              粘贴完整的启动链接
              <input
                type="password"
                aria-label="完整启动链接"
                autoComplete="off"
                value={login}
                onChange={(e) => setLogin(e.target.value)}
              />
            </label>
            <button className="primary" disabled={!login.trim()}>
              连接工作台
            </button>
          </form>
        </details>
        {error && <p role="alert">{error}</p>}
      </main>
    );
  return (
    <div
      className={
        "app-shell" +
        (sidebarHidden ? " sidebar-hidden" : "") +
        (immersive ? " immersive" : "")
      }
    >
      <aside className="sidebar" id="paper-library" hidden={sidebarHidden}>
        <div className="brand">
          <div className="brand-mark">
            <BookOpen size={20} />
          </div>
          <div>
            Paper Research<span>COACH</span>
          </div>
        </div>
        <div className="sidebar-intro">阅读，始于一个好问题。</div>
        <nav>
          {nav
            .filter(([id]) => id === "read" || id === "review")
            .map(([id, label, Icon]) => (
              <button
                key={id}
                className={tab === id ? "selected" : ""}
                onClick={() => setTab(id)}
              >
                <Icon size={17} />
                {label}
                {id === "read" && <span className="nav-indicator" />}
              </button>
            ))}
          <details
            className="library-secondary"
            open={tab === "lineage" || tab === "ideas" || tab === "export"}
          >
            <summary>
              研究与记录 <ChevronDown size={14} />
            </summary>
            {nav
              .filter(([id]) => id !== "read" && id !== "review")
              .map(([id, label, Icon]) => (
                <button
                  key={id}
                  className={tab === id ? "selected" : ""}
                  onClick={() => setTab(id)}
                >
                  <Icon size={17} />
                  {label}
                </button>
              ))}
          </details>
        </nav>
        <div className="library-heading">
          <h2>我的论文</h2>
          <button aria-label="导入论文" onClick={() => setImporting(true)}>
            <Plus size={17} />
          </button>
        </div>
        <div className="search">
          <Search size={14} />
          <input
            aria-label="查找论文"
            placeholder="标题、作者、年份…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="paper-list">
          {visiblePapers.map((p: Row) => (
              <button
                key={p.id}
                className={selected === p.id ? "current" : ""}
                onClick={() => select(p.id)}
              >
                <span className={"paper-dot " + p.status} />
                <div>
                  <strong>{p.title}</strong>
                  <small>
                    {p.year || "未标年份"} ·{" "}
                    {
                      (
                        {
                          queued: "待读",
                          reading: "阅读中",
                          paused: "已暂停",
                          done: "已完成",
                        } as any
                      )[p.status]
                    }
                  </small>
                  <TranslationBadge job={translationIndex[p.id]} />
                </div>
              </button>
            ))}
          {!!state.papers.length && !visiblePapers.length && (
            <div className="library-empty" role="status">
              <p>没有找到“{search}”</p>
              <small>试试标题、作者、年份或 DOI。</small>
              <button className="text-button" onClick={() => setSearch("")}>清除搜索</button>
            </div>
          )}
          {!state.papers.length && (
            <p className="muted small">
              导入第一篇论文，
              <br />
              从你当前的问题开始。
            </p>
          )}
        </div>
        <button
          className={
            "settings-button " + (tab === "settings" ? "selected" : "")
          }
          onClick={() => setTab("settings")}
        >
          <SettingsIcon size={16} />
          Zotero 与设置
          <span
            className={
              "status-dot " + (state.sync.state === "connected" ? "online" : "")
            }
          />
        </button>
        <div className="local-label">所有笔记 · 本机保存</div>
      </aside>
      <main
        className={
          "main-shell " + (paper && tab === "read" ? "reading-open" : "")
        }
      >
        <header className={"topbar" + (immersive ? " immersive-controls" : "")}>
          <button
            className="sidebar-toggle"
            aria-label={sidebarHidden ? "显示论文栏" : "隐藏论文栏"}
            aria-expanded={!sidebarHidden}
            aria-controls="paper-library"
            onClick={() => {
              setSidebarHidden(!sidebarHidden);
              localStorage.setItem(
                "prc-sidebar-hidden",
                String(!sidebarHidden),
              );
            }}
          >
            {sidebarHidden ? (
              <PanelLeftOpen size={18} />
            ) : (
              <PanelLeftClose size={18} />
            )}
          </button>
          <span className="topbar-title" title={paper?.title}>
            {paper?.title || "论文工作台"}
          </span>
          {paper && tab === "read" ? (
            <div className="reading-toolbar">
              <button
                className="immersive-toggle"
                aria-pressed={immersive}
                aria-label={immersive ? "退出沉浸模式" : "进入沉浸模式"}
                title="⌘ / Ctrl + Shift + Enter"
                onClick={immersiveToggle}
              >
                {immersive ? <Minimize2 size={17} /> : <Maximize2 size={17} />}
              </button>
              <button aria-label="更多阅读工具" onClick={() => openTools()}>
                <MoreHorizontal size={20} />
              </button>
            </div>
          ) : tab !== "read" ? (
            <button onClick={() => setTab("read")}>返回阅读</button>
          ) : null}
        </header>
        {error && (
          <div className="toast" role="status">
            <span>{error}</span>
            <button aria-label="关闭提示" onClick={() => setError("")}>
              <X size={16} />
            </button>
          </div>
        )}
        {tab === "settings" ? (
          <Settings
            state={state}
            refresh={() => void refresh()}
            report={report}
            onTranslationUpdate={() => void reloadTranslation()}
            onReadTranslated={(pid) => {
              translatedRead.current = pid;
              select(pid);
              setTab("read");
              if (pid === paper?.id) void reloadTranslation();
            }}
          />
        ) : !paper ? (
          <Welcome onImport={() => setImporting(true)} onConnect={() => setTab("settings")} />
        ) : (
          <>
            <div className="paper-heading">
              <div>
                <span className="eyebrow">
                  {stages[session?.stage] || "开始阅读"}{" "}
                  <span className="stage-dot">·</span>{" "}
                  {
                    (
                      {
                        skim: "快速判断",
                        understand: "理解贡献",
                        reconstruct: "深入重建",
                      } as any
                    )[session?.depth]
                  }
                </span>
                <h1>{paper.title}</h1>
                <p>
                  {paper.authors || "作者信息待补充"}{" "}
                  {paper.year && " / " + paper.year}
                  {paper.publication && " / " + paper.publication}
                </p>
              </div>
              <div className="button-row">
                {tab !== "read" && (
                  <button
                    className="subtle"
                    onClick={() => {
                      setTab("read");
                      setReadingPane("coach");
                    }}
                  >
                    <MessageCircle size={15} />
                    与教练讨论
                  </button>
                )}
                <button className="subtle" onClick={pause}>
                  {paper.status === "paused" ? (
                    <Play size={15} />
                  ) : (
                    <Pause size={15} />
                  )}{" "}
                  {paper.status === "paused" ? "恢复阅读" : "暂停并保存"}
                </button>
                <details className="paper-tools">
                  <summary aria-label="更多论文操作" title="更多论文操作">
                    <MoreHorizontal size={19} />
                  </summary>
                  <div className="paper-tools-menu">
                    <button
                      onClick={(e) => {
                        setPaperEditor({ ...paper });
                        e.currentTarget
                          .closest("details")
                          ?.removeAttribute("open");
                      }}
                    >
                      论文信息与版本
                    </button>
                    <button
                      onClick={(e) => {
                        setTaskEditor({ ...session });
                        e.currentTarget
                          .closest("details")
                          ?.removeAttribute("open");
                      }}
                    >
                      阅读目标与深度
                    </button>
                    <button
                      onClick={(e) => {
                        setTab("export");
                        e.currentTarget
                          .closest("details")
                          ?.removeAttribute("open");
                      }}
                    >
                      导出阅读记录
                    </button>
                  </div>
                </details>
              </div>
            </div>
            {tab === "read" ? (
              <>
                {readingPane === "notes" && (
                  <details className="current-task note-reading-task">
                    <summary>
                      阅读主线 · {stages[session?.stage] || "开始阅读"}
                    </summary>
                    <div className="task-number">01</div>
                    <div>
                      <span className="eyebrow">现在只做这一件事</span>
                      <p>
                        {session?.next_action ||
                          "点击右侧“开始跟读”，按这篇论文的阅读主线逐步形成判断。"}
                      </p>
                      {session?.pending_question && (
                        <span className="muted small">
                          正在想：{session.pending_question}
                        </span>
                      )}
                    </div>
                    <button
                      title="调整当前阅读任务"
                      onClick={() => setTaskEditor({ ...session })}
                    >
                      <ChevronDown size={18} />
                    </button>
                  </details>
                )}
                <div
                  className="reading-layout"
                  ref={layout}
                  style={{
                    gridTemplateColumns: `minmax(400px, ${split * 100}fr) 6px minmax(320px, ${(1 - split) * 100}fr)`,
                  }}
                >
                  {paper.source_path ? (
                    <PdfReader
                      paper={paper}
                      page={page}
                      setPage={movePage}
                      onAnchor={(a, placement) => {
                        setAnchor(a);
                          setSelection({
                            id: id(),
                            anchor: a,
                            view: pdfView,
                            x: placement?.x || 40,
                            y: placement?.y || 100,
                          });
                      }}
                      toolsContainer={pdfTools}
                      fileUrl={
                        pdfView !== "original" &&
                        hasTranslation(translationPdfJob)
                          ? `/api/translation/jobs/${translationPdfJob.id}/pdf/${pdfView}`
                          : undefined
                      }
                      documentKey={
                        pdfView === "original"
                          ? "original"
                          : translationPdfJob?.id + ":" + pdfView + ":" + translationPdfJob?.documents?.[pdfView]?.document_version
                      }
                      derived={pdfView !== "original"}
                      rendition={pdfView !== "original" && translationPdfJob?.documents?.[pdfView] ? {
                        job_id: translationPdfJob.id, view: pdfView, document_version: translationPdfJob.documents[pdfView].document_version,
                      } : null}
                      draftAnchor={selection?.id === markedSelection ? null : selection?.anchor}
                      onExport={() => void exportCurrentPdf()}
                      exporting={exportingPdf}
                      focusAnchor={focusAnchor}
                      notes={context.notes || []}
                      onLocateNote={locate}
                    />
                  ) : (
                    <div className="reader empty">
                      <BookOpen size={28} />
                      <h3>目前只有书目信息</h3>
                      <p>获取全文后再核实方法与证据。你仍可以记录研究问题。</p>
                      <label>
                        已有本地 PDF 的完整路径
                        <input
                          placeholder="/path/to/paper.pdf"
                          onKeyDown={async (e) => {
                            if (e.key === "Enter")
                              try {
                                await api("source/" + paper.id, {
                                  path: e.currentTarget.value,
                                });
                                await refresh();
                              } catch (err) {
                                report(String(err));
                              }
                          }}
                        />
                      </label>
                      <p className="small">输入后按回车连接 PDF。</p>
                    </div>
                  )}
                  <div
                    className="reading-divider"
                    role="separator"
                    aria-label="调整 PDF 与对话宽度"
                    aria-orientation="vertical"
                    aria-valuemin={45}
                    aria-valuemax={80}
                    aria-valuenow={Math.round(split * 100)}
                    tabIndex={0}
                    onPointerDown={(e) =>
                      e.currentTarget.setPointerCapture(e.pointerId)
                    }
                    onPointerMove={(e) => {
                      if (
                        e.currentTarget.hasPointerCapture(e.pointerId) &&
                        layout.current
                      ) {
                        const b = layout.current.getBoundingClientRect();
                        ratio((e.clientX - b.left) / b.width);
                      }
                    }}
                    onPointerUp={(e) => {
                      if (e.currentTarget.hasPointerCapture(e.pointerId))
                        e.currentTarget.releasePointerCapture(e.pointerId);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
                        e.preventDefault();
                        ratio(split + (e.key === "ArrowLeft" ? -0.02 : 0.02));
                      }
                    }}
                  />
                  <aside className="research-pane">
                    <div className="coach-surface">
                      <CoachPanel
                        key={paper.id + launchConversation}
                        initialConversation={launchConversation}
                        toolsContainer={coachTools}
                        onOpenTools={() => openTools("coach")}
                        paper={paper}
                        context={context}
                        page={page}
                        anchor={anchor}
                        onClearAnchor={() => {
                          setAnchor(null);
                          setSelection(null);
                        }}
                        onLocate={locate}
                        onAction={(kind) => {
                          if (kind === "idea") setTab("ideas");
                          else if (kind === "review") setTab("review");
                          else if (kind === "note") openTools("notes");
                        }}
                        refresh={() => void refresh()}
                        report={report}
                      />
                    </div>
                  </aside>
                </div>
                <aside
                  className="reading-drawer"
                  hidden={!toolsOpen}
                  aria-label="阅读工具抽屉"
                >
                  <header>
                    <strong>阅读工具</strong>
                    <button
                      disabled={
                        syncBusy ||
                        (!state?.sync?.collection && !state?.vault?.root)
                      }
                      onClick={() => void refreshSync()}
                      title="立即同步 Zotero 和文献目录"
                    >
                      {syncBusy ? "正在刷新…" : "刷新同步"}
                    </button>
                    {immersive && (
                      <button
                        onClick={() => {
                          setImmersive(false);
                          setToolsOpen(false);
                        }}
                      >
                        退出沉浸
                      </button>
                    )}
                    <button
                      aria-label="关闭阅读工具"
                      onClick={closeTools}
                    >
                      <X size={18} />
                    </button>
                  </header>
                  <nav aria-label="阅读工具分类">
                    {[
                      ["translate", "翻译"],
                      ["coach", "教练"],
                      ["notes", "笔记"],
                      ["paper", "更多"],
                    ].map(([value, label]) => (
                      <button
                        key={value}
                        aria-pressed={toolsTab === value}
                        onClick={() => setToolsTab(value)}
                      >
                        {label}
                      </button>
                    ))}
                  </nav>
                  <div className="drawer-body">
                    {syncError && <p role="alert">{syncError}</p>}
                    <div hidden={toolsTab !== "translate"}>
                      <TranslationTools
                        paper={paper}
                        job={translationJob}
                        readableJob={translationPdfJob}
                        reload={() => void reloadTranslation()}
                        view={pdfView}
                        setView={(v) => {
                          setPdfView(v);
                          setSelection(null);
                          setAnchor(null);
                        }}
                        open={toolsOpen && toolsTab === "translate"}
                      />
                      <button
                        className="text-button"
                        onClick={() => {
                          setToolsOpen(false);
                          setImmersive(false);
                          setTab("settings");
                        }}
                      >
                        打开文献库，批量后台翻译
                      </button>
                    </div>
                    <section
                      ref={setCoachTools}
                      hidden={toolsTab !== "coach"}
                    />
                    <div hidden={toolsTab !== "notes"}>
                      <Notes
                        key={paper.id}
                        paper={paper}
                        notes={context.notes}
                        anchor={anchor}
                        newNoteRequest={newNoteRequest}
                        onLocate={locate}
                        refresh={() => void refresh()}
                        report={report}
                      />
                    </div>

                    <section hidden={toolsTab !== "paper"}>
                      <h3>论文与阅读</h3>
                      <button onClick={() => setTaskEditor({ ...session })}>
                        阅读目标与深度
                      </button>
                      <button onClick={() => setPaperEditor({ ...paper })}>
                        论文信息与版本
                      </button>
                      <button onClick={() => void pause()}>
                        {paper.status === "paused" ? "恢复阅读" : "暂停并保存"}
                      </button>
                      <h3>PDF 工具</h3>
                      <div ref={setPdfTools} />
                      <h3>研究与设置</h3>
                      {nav
                        .filter(([id]) => id !== "read")
                        .map(([id, label]) => (
                          <button
                            key={id}
                            onClick={() => {
                              setToolsOpen(false);
                              setImmersive(false);
                              setTab(id);
                            }}
                          >
                            {label}
                          </button>
                        ))}
                      <button
                        onClick={() => {
                          setToolsOpen(false);
                          setImmersive(false);
                          setTab("settings");
                        }}
                      >
                        Zotero、同步与设置
                      </button>
                    </section>
                  </div>
                </aside>
                {selection && (
                  <TranslationPopover
                    key={selection.id}
                    selection={selection}
                    job={translationPdfJob}
                    onClose={() => setSelection(null)}
                    onSource={(a) => {
                      if (selection.view !== "original") setAnchor(a);
                    }}
                    onMark={async (a) => {
                      await put("note", { id: selection.id, paper_id: paper.id, revision: 0, author: "user", provenance: "USER", content: anchorQuote(a) || "区域标记", anchor: a, annotation_type: anchorQuote(a) ? "highlight" : "rectangle" }, selection.id);
                      await refresh();
                      setMarkedSelection(selection.id);
                    }}
                    onNote={(a) => {
                      setAnchor(a); setNewNoteRequest({ id: id(), anchor: a }); openTools("notes");
                      requestAnimationFrame(() => document.querySelector<HTMLTextAreaElement>('textarea[aria-label="记录想法"]')?.focus());
                    }}
                    onDiscuss={(a) => {
                      setAnchor(a);
                      setSelection(null);
                      document
                        .querySelector<HTMLTextAreaElement>(
                          ".coach-compose textarea",
                        )
                        ?.focus();
                    }}
                  />
                )}
              </>
            ) : tab === "lineage" ? (
              <Lineage
                seq={context?.seq}
                key={paper.id}
                paper={paper}
                papers={state.papers}
                refresh={() => void refresh()}
                report={report}
                onSelect={select}
              />
            ) : tab === "ideas" ? (
              <Ideas
                seq={context?.seq}
                key={paper.id}
                paper={paper}
                report={report}
              />
            ) : tab === "review" ? (
              <Reviews
                seq={context?.seq}
                key={paper.id}
                paper={paper}
                report={report}
                onLocate={locate}
              />
            ) : (
              <Exports paper={paper} report={report} />
            )}
          </>
        )}
      </main>
      {importing && (
        <ImportModal
          onClose={() => setImporting(false)}
          onDone={async (p: Row) => {
            setImporting(false);
            select(p.id);
            await refresh();
          }}
          report={report}
        />
      )}
      {paperEditor && (
        <PaperEditor
          paper={paperEditor}
          onClose={() => setPaperEditor(null)}
          onDone={async () => {
            setPaperEditor(null);
            await refresh();
          }}
          report={report}
        />
      )}
      {taskEditor && (
        <Dialog label="当前阅读任务" onClose={() => setTaskEditor(null)}>
            <span className="eyebrow">允许跳读、返回或改变深度</span>
            <h2>当前阅读任务</h2>
            <label>
              我的目标
              <textarea
                value={taskEditor.goal}
                onChange={(e) =>
                  setTaskEditor({ ...taskEditor, goal: e.target.value })
                }
              />
            </label>
            <div className="form-grid">
              <label>
                阅读阶段
                <select
                  value={taskEditor.stage}
                  onChange={(e) =>
                    setTaskEditor({ ...taskEditor, stage: e.target.value })
                  }
                >
                  {Object.entries(stages).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                需要多深入
                <select
                  value={taskEditor.depth}
                  onChange={(e) =>
                    setTaskEditor({ ...taskEditor, depth: e.target.value })
                  }
                >
                  <option value="skim">快速判断</option>
                  <option value="understand">理解贡献</option>
                  <option value="reconstruct">深入重建</option>
                </select>
              </label>
            </div>
            <label>
              下一步只做什么
              <textarea
                value={taskEditor.next_action}
                onChange={(e) =>
                  setTaskEditor({ ...taskEditor, next_action: e.target.value })
                }
              />
            </label>
            <label>
              还没想清楚的问题
              <textarea
                value={taskEditor.pending_question}
                onChange={(e) =>
                  setTaskEditor({
                    ...taskEditor,
                    pending_question: e.target.value,
                  })
                }
              />
            </label>
            <label className="check-label">
              <input
                type="checkbox"
                checked={taskEditor.note_consent}
                onChange={(e) =>
                  setTaskEditor({
                    ...taskEditor,
                    note_consent: e.target.checked,
                  })
                }
              />
              允许教练保存我在对话中说出的原话
            </label>
            <p className="small muted">
              对话记录与主动输入的笔记始终保存。此选项控制是否额外生成对话原话笔记。
            </p>
            <div className="button-row">
              <button
                className="primary"
                onClick={async () => {
                  try {
                    await put("session", taskEditor);
                    setTaskEditor(null);
                    await refresh();
                  } catch (e) {
                    report(String(e));
                  }
                }}
              >
                保存并继续
              </button>
              <button onClick={() => setTaskEditor(null)}>取消</button>
            </div>
        </Dialog>
      )}
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);

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
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { api, ApiError, put, anchorFor, type Row } from "./api";
import { readLaunchInput } from "./launch";
import PdfReader from "./PdfReader";
import Notes from "./Notes";
import CoachPanel from "./Coach";
import { Lineage, Ideas, Reviews, Settings, Exports } from "./Panels";
import "./style.css";
import "./quiet-reading.css";
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
  const [fitRequest, setFitRequest] = useState(0);
  const [split, setSplit] = useState(() =>
    Math.max(
      0.45,
      Math.min(0.8, Number(localStorage.getItem("prc-pane-ratio")) || 0.7),
    ),
  );
  const [translationJob, setTranslationJob] = useState<any>(null);
  const [translationPdfJob, setTranslationPdfJob] = useState<any>(null);
  const [translationIndex, setTranslationIndex] = useState<any>({});
  const translatedRead = useRef("");
  const [pdfView, setPdfView] = useState<PdfView>("original");
  const [selection, setSelection] = useState<any>(null);
  const layout = useRef<HTMLDivElement>(null);
  function openTools(section = "translate") {
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
      if (e.defaultPrevented) return;
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === "Enter") {
        e.preventDefault();
        immersiveToggle();
      }
      if (e.key === "Escape") {
        if (toolsOpen) {
          e.preventDefault();
          setToolsOpen(false);
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
      const readable = result.papers?.[pid];
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
        "prc-page-" + paper.id + ":" + paper.source_version,
        String(n),
      );
    setPage(n);
    setFocusAnchor(null);
    clearTimeout(pageTimer.current);
    const pid = selectedRef.current;
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
  function locate(a: any) {
    setPdfView("original");
    if (a.status === "stale" || a.source_version !== paper.source_version) {
      report("这条笔记属于旧版本。原话仍在，请重新核实位置。");
      return;
    }
    if (a.page_index === null) {
      report("这条笔记尚未定位到具体页面。");
      return;
    }
    setTab("read");
    movePage(a.page_index);
    setFocusAnchor(a);
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
            placeholder="查找论文…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="paper-list">
          {state.papers
            .filter((p: Row) =>
              p.title.toLowerCase().includes(search.toLowerCase()),
            )
            .map((p: Row) => (
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
              <div className="compact-pages">
                <button
                  aria-label="上一页"
                  disabled={page <= 0}
                  onClick={() => movePage(page - 1)}
                >
                  <ChevronLeft size={16} />
                </button>
                <input
                  aria-label="阅读页码"
                  type="number"
                  min={1}
                  max={paper.page_count || 1}
                  value={page + 1}
                  onChange={(e) => {
                    const n = Number(e.target.value);
                    if (Number.isFinite(n))
                      movePage(
                        Math.max(0, Math.min(paper.page_count - 1, n - 1)),
                      );
                  }}
                />
                <span>/ {paper.page_count}</span>
                <button
                  aria-label="下一页"
                  disabled={page >= paper.page_count - 1}
                  onClick={() => movePage(page + 1)}
                >
                  <ChevronRight size={16} />
                </button>
              </div>
              <button
                onClick={() => setFitRequest((v) => v + 1)}
                aria-label="PDF 适宽"
              >
                适宽
              </button>
              <button
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
          ) : (
            <button onClick={() => setTab("read")}>返回阅读</button>
          )}
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
          <div className="welcome">
            <span className="eyebrow">从一篇值得读的论文开始</span>
            <h1>
              把阅读变成
              <br />
              自己的研究判断。
            </h1>
            <p>
              打开论文，留下直觉，在工作台里一起检验。
              <br />
              一次推进一个问题，不急着读完全部。
            </p>
            <button className="primary" onClick={() => setImporting(true)}>
              <Plus size={17} />
              导入论文
            </button>
            <button className="text-button" onClick={() => setTab("settings")}>
              连接 Zotero <ArrowRight size={16} />
            </button>
          </div>
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
                        if (pdfView === "original") setAnchor(a);
                        else setAnchor(null);
                        if (a.quote)
                          setSelection({
                            anchor: a,
                            view: pdfView,
                            x: placement?.x || 40,
                            y: placement?.y || 100,
                          });
                      }}
                      toolsContainer={pdfTools}
                      fitRequest={fitRequest}
                      fileUrl={
                        pdfView !== "original" &&
                        hasTranslation(translationPdfJob)
                          ? `/api/translation/jobs/${translationPdfJob.id}/pdf/${pdfView}`
                          : undefined
                      }
                      documentKey={
                        pdfView === "original"
                          ? "original"
                          : translationPdfJob?.id + ":" + pdfView
                      }
                      derived={pdfView !== "original"}
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
                      onClick={() => setToolsOpen(false)}
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
                    selection={selection}
                    job={translationPdfJob}
                    onClose={() => setSelection(null)}
                    onSource={(a) => {
                      if (selection.view !== "original") setAnchor(a);
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
        <div className="modal-backdrop">
          <div className="modal">
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
          </div>
        </div>
      )}
    </div>
  );
}
function PaperEditor({
  paper,
  onClose,
  onDone,
  report,
}: {
  paper: Row;
  onClose: () => void;
  onDone: () => void;
  report: (s: string) => void;
}) {
  const [value, setValue] = useState(paper),
    [file, setFile] = useState<File | null>(null),
    [path, setPath] = useState(paper.source_path || ""),
    [busy, setBusy] = useState(false);
  return (
    <div className="modal-backdrop">
      <div className="modal">
        <h2>论文信息与版本</h2>
        <div className="form-grid">
          {[
            ["title", "论文名称"],
            ["authors", "作者"],
            ["year", "年份"],
            ["doi", "DOI"],
            ["url", "来源链接"],
            ["goal", "阅读目标"],
          ].map(([k, label]) => (
            <label key={k}>
              {label}
              <input
                value={value[k]}
                onChange={(e) => setValue({ ...value, [k]: e.target.value })}
              />
            </label>
          ))}
          <label>
            论文类型
            <select
              value={value.paper_type}
              onChange={(e) =>
                setValue({ ...value, paper_type: e.target.value })
              }
            >
              {[
                ["empirical", "实证 / 算法"],
                ["theory", "理论"],
                ["measurement", "测量"],
                ["dataset", "数据集"],
                ["survey", "综述"],
                ["systems", "系统工程"],
              ].map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <label>
            阅读状态
            <select
              value={value.status}
              onChange={(e) => setValue({ ...value, status: e.target.value })}
            >
              {[
                ["queued", "待读"],
                ["reading", "阅读中"],
                ["paused", "暂停"],
                ["done", "已完成"],
              ].map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
        </div>
        <button
          className="primary"
          disabled={busy}
          onClick={async () => {
            try {
              await put("paper", value);
              onDone();
            } catch (e) {
              report(String(e));
            }
          }}
        >
          保存信息
        </button>
        <div className="divider" />
        <h3>确认 PDF 版本</h3>
        <p className="small muted">
          换版会保留旧笔记，将旧位置标为待重新核实。不会修改原始 PDF。
        </p>
        <label>
          本地 PDF 路径
          <input value={path} onChange={(e) => setPath(e.target.value)} />
        </label>
        <label>
          或选择新版 PDF
          <input
            type="file"
            accept=".pdf,application/pdf"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
        </label>
        <div className="button-row">
          <button
            disabled={busy || (!path && !file)}
            onClick={async () => {
              setBusy(true);
              try {
                if (file) {
                  const r = await fetch("/api/upload?replace=" + paper.id, {
                    method: "POST",
                    headers: { "Content-Type": "application/pdf" },
                    body: file,
                  });
                  if (!r.ok) throw new Error((await r.json()).error);
                } else await api("source/" + paper.id, { path });
                onDone();
                report("已确认来源版本；旧位置需要重新核实");
              } catch (e) {
                report(String(e));
              } finally {
                setBusy(false);
              }
            }}
          >
            确认此 PDF 版本
          </button>
          <button onClick={onClose}>关闭</button>
        </div>
      </div>
    </div>
  );
}
function ImportModal({
  onClose,
  onDone,
  report,
}: {
  onClose: () => void;
  onDone: (p: Row) => void;
  report: (s: string) => void;
}) {
  const [title, setTitle] = useState(""),
    [path, setPath] = useState(""),
    [goal, setGoal] = useState(""),
    [file, setFile] = useState<File | null>(null),
    [busy, setBusy] = useState(false);
  async function submit() {
    setBusy(true);
    try {
      let p;
      if (file) {
        const r = await fetch(
          "/api/upload?title=" +
            encodeURIComponent(title || file.name.replace(/\.pdf$/i, "")),
          {
            method: "POST",
            headers: { "Content-Type": "application/pdf" },
            body: file,
          },
        );
        p = await r.json();
        if (!r.ok) throw new Error(p.error || "无法读取 PDF");
        if (goal) p = await put("paper", { ...p, goal });
      } else p = await api("import", { title, path, goal });
      onDone(p);
    } catch (e) {
      report(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="modal-backdrop">
      <div className="modal">
        <div className="panel-title">
          <h2>打开一篇论文</h2>
          <button aria-label="关闭导入" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        <label className="file-drop">
          <BookOpen size={26} />
          <span>{file ? file.name : "选择 PDF 文件"}</span>
          <input
            type="file"
            accept="application/pdf,.pdf"
            onChange={(e) => {
              const f = e.target.files?.[0] || null;
              setFile(f);
              if (f && !title) setTitle(f.name.replace(/\.pdf$/i, ""));
            }}
          />
        </label>
        <label>
          论文名称
          <input value={title} onChange={(e) => setTitle(e.target.value)} />
        </label>
        <label>
          这次阅读为了什么？
          <textarea
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder="例如：判断这个方法是否适合我的问题"
          />
        </label>
        <details>
          <summary>或使用已有本地路径</summary>
          <input
            placeholder="/path/to/paper.pdf"
            value={path}
            onChange={(e) => setPath(e.target.value)}
          />
          <p className="small muted">
            只建立只读连接。也可以不填路径，先保存论文书目。
          </p>
        </details>
        <button
          className="primary"
          disabled={busy || !title.trim()}
          onClick={submit}
        >
          {busy ? "正在导入…" : "开始阅读"}
          <ArrowRight size={16} />
        </button>
      </div>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);

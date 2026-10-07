import { createPortal } from "react-dom";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  ArrowUp,
  Square,
  MessageCircle,
  MapPin,
  RefreshCw,
  X,
  Plus,
  Maximize2,
  Minimize2,
} from "lucide-react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
// CommonMark ignores **加粗：**正文 when a closing ** follows CJK punctuation.
import remarkCjkFriendly from "remark-cjk-friendly";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import {
  api,
  ApiError,
  id,
  location,
  sameAnchor,
  anchorFor,
  anchorQuote,
  type Row,
} from "./api";
import {
  contextPage,
  imageMatchesPage,
  replyIntent,
  helpLabels,
  type HelpMode,
  type IntentChoice,
} from "./reading-context";

type Message = {
  id: string;
  role: string;
  content: string;
  status: string;
  error?: string;
  anchor?: any;
  imported?: boolean;
  actions?: any[];
  connection_notice?: string;
  intent?: string;
  help_mode?: HelpMode;
  context_scope?: {
    notes_included: number;
    notes_total: number;
    page_index: number | null;
    history_messages_included: number;
  };
};
type Snapshot = {
  conversation_id: string;
  conversations: Row[];
  messages: Message[];
  busy: boolean;
  read_only?: boolean;
  canonical_conversation_id?: string;
  thread_id?: string;
  reading_flow?: any;
};

function prose(text: string) {
  return text
    .replace(/\\\[([\s\S]*?)\\\]/g, "\n$$$$\n$1\n$$$$\n")
    .replace(/\\\(([\s\S]*?)\\\)/g, "$$$1$$");
}

export default function CoachPanel({
  paper,
  context,
  page,
  anchor,
  onClearAnchor,
  onLocate,
  onAction,
  refresh,
  report,
  initialConversation = "",
  toolsContainer,
  onOpenTools,
}: {
  paper: Row;
  context: any;
  page: number;
  anchor: any;
  onClearAnchor: () => void;
  onLocate: (a: any) => void;
  onAction: (kind: string) => void;
  refresh: () => void;
  report: (s: string) => void;
  initialConversation?: string;
  toolsContainer?: HTMLElement | null;
  onOpenTools?: () => void;
}) {
  const key = "prc-chat-draft-" + paper.id;
  const jobKey = "prc-chat-send-" + paper.id;
  const [text, setText] = useState(() => localStorage.getItem(key) || "");
  const [snapshot, setSnapshot] = useState<Snapshot>({
    conversation_id: "",
    conversations: [],
    messages: [],
    busy: false,
  });
  const [chosen, setChosen] = useState(initialConversation);
  const [status, setStatus] = useState<any>(null);
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const [pending, setPending] = useState(() => !!localStorage.getItem(jobKey));
  const [model, setModel] = useState(
    () => localStorage.getItem("prc-coach-model") || "",
  );
  const [effort, setEffort] = useState(
    () => localStorage.getItem("prc-coach-effort") || "",
  );
  const [expanded, setExpanded] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [includeImage, setIncludeImage] = useState(false);
  const [intentChoice, setIntentChoice] = useState<IntentChoice>("auto");
  const [helpMode, setHelpMode] = useState<HelpMode>("guided");
  const currentAnchor = useRef(anchor);
  currentAnchor.current = anchor;
  const effectiveIntent = replyIntent(
    snapshot.reading_flow,
    anchor,
    intentChoice,
  );
  const canAttachImage = imageMatchesPage(paper, page, anchor);
  const scroll = useRef<HTMLDivElement>(null);
  const composer = useRef<HTMLTextAreaElement>(null);
  const atBottom = useRef(true);
  const alive = useRef(true);
  const currentText = useRef(text);
  currentText.current = text;
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  useEffect(() => {
    let disposed = false;
    const events = new EventSource(
      "/api/coach/events/" +
        paper.id +
        (chosen ? "?conversation_id=" + encodeURIComponent(chosen) : ""),
    );
    const apply = (s: Snapshot) => {
      if (!disposed) setSnapshot(s);
    };
    events.onmessage = (e) => {
      try {
        apply(JSON.parse(e.data));
      } catch {}
    };
    void api(
      "coach/conversation/" +
        paper.id +
        (chosen ? "?conversation_id=" + encodeURIComponent(chosen) : ""),
    )
      .then(apply)
      .catch((e) => {
        if (!disposed) setError(String(e));
      });
    // A reconnect always reads durable state; it never resends a model turn.
    events.onopen = () =>
      void api(
        "coach/conversation/" +
          paper.id +
          (chosen ? "?conversation_id=" + encodeURIComponent(chosen) : ""),
      )
        .then(apply)
        .catch(() => {});
    return () => {
      disposed = true;
      events.close();
    };
  }, [paper.id, chosen]);
  useEffect(() => {
    let disposed = false;
    const update = () =>
      api("coach/status")
        .then((s) => {
          if (!disposed) setStatus(s);
        })
        .catch(() => {
          if (!disposed)
            setStatus({ state: "unavailable", message: "CLI 连接暂不可用" });
        });
    void update();
    const timer = setInterval(
      () => {
        void update();
      },
      status?.state === "login_required" ? 4000 : 20000,
    );
    return () => {
      disposed = true;
      clearInterval(timer);
    };
  }, [status?.state]);
  useEffect(() => {
    if (atBottom.current && scroll.current)
      scroll.current.scrollTop = scroll.current.scrollHeight;
  }, [snapshot.messages]);
  useEffect(() => {
    setIncludeImage(
      !!anchor?.rects?.length &&
        !anchor?.quote &&
        imageMatchesPage(paper, page, anchor),
    );
    setIntentChoice("auto");
  }, [anchor, page, paper.id, paper.source_version, chosen]);
  // Grow with the draft up to a bounded height, so long answers stay visible.
  useLayoutEffect(() => {
    const t = composer.current;
    if (!t) return;
    t.style.height = "auto";
    t.style.height = Math.min(t.scrollHeight + 2, 260) + "px";
  }, [text]);
  function change(value: string) {
    setText(value);
    localStorage.setItem(key, value);
  }
  function pageImage() {
    const canvas = document.querySelector<HTMLCanvasElement>(
      `.pdf-page[data-paper-id="${paper.id}"][data-source-version="${paper.source_version}"][data-page-index="${page}"] canvas`,
    );
    if (!canvas) throw new Error("当前页还未打开。稍后重试，或取消附上图表。");
    const image = document.createElement("canvas");
    const ratio = Math.min(1, 1400 / canvas.width);
    image.width = Math.round(canvas.width * ratio);
    image.height = Math.round(canvas.height * ratio);
    image.getContext("2d")?.drawImage(canvas, 0, 0, image.width, image.height);
    const png = image.toDataURL("image/png");
    return png.length > 3500000 ? image.toDataURL("image/jpeg", 0.85) : png;
  }
  async function send(
    content = text,
    retry = false,
    intent = effectiveIntent as string,
  ) {
    if (
      snapshot.read_only ||
      status?.state !== "ready" ||
      sending ||
      connecting ||
      snapshot.busy ||
      (!retry && intent !== "follow" && !content.trim())
    )
      return;
    if (pending && !retry) {
      setError("上次发送的结果还未确认。先点击确认上次发送，可避免重复提问。");
      return;
    }
    let body: any;
    try {
      if (!retry && intent !== "follow" && includeImage && !canAttachImage)
        throw new Error("图表与选区不在同一页，请先回到选区位置。");
      body = retry
        ? JSON.parse(localStorage.getItem(jobKey) || "null")
        : {
            operation_id: id(),
            conversation_id: snapshot.conversation_id,
            content,
            intent,
            anchor: intent === "follow" ? null : anchor,
            page_index:
              intent === "follow" ? page : contextPage(paper, page, anchor),
            source_version: paper.source_version,
            help_mode: helpMode,
            model,
            effort,
            page_image: intent !== "follow" && includeImage ? pageImage() : "",
          };
      if (!body) return;
      // Persist the exact request before crossing the network.
      localStorage.setItem(jobKey, JSON.stringify(body));
      setPending(true);
      setSending(true);
      setError("");
      atBottom.current = true;
      const result = await api("coach/send/" + paper.id, body);
      localStorage.removeItem(jobKey);
      if (!alive.current) return;
      setPending(false);
      setChosen(result.conversation_id);
      if (currentText.current === body.content) change("");
      // Do not clear a newer selection made while the request was in flight.
      if (body.anchor && sameAnchor(currentAnchor.current, body.anchor)) {
        onClearAnchor();
        setIncludeImage(false);
      }
      setSnapshot(
        await api(
          "coach/conversation/" +
            paper.id +
            "?conversation_id=" +
            result.conversation_id,
        ),
      );
    } catch (e) {
      if (e instanceof ApiError && e.status >= 400 && e.status < 500) {
        localStorage.removeItem(jobKey);
        if (alive.current) setPending(false);
      }
      if (alive.current) setError(String(e));
    } finally {
      if (alive.current) setSending(false);
    }
  }
  async function chooseConversation(conversationId: string, fresh = false) {
    if (snapshot.busy || pending || connecting || sending) return;
    setConnecting(true);
    setError("");
    try {
      const c = fresh
        ? await api("coach/connect/" + paper.id, { new: true })
        : { id: conversationId };
      if (!c.id || c.id === snapshot.canonical_conversation_id)
        await api("coach/active", {
          paper_id: paper.id,
          conversation_id: c.id,
        });
      const next = await api(
        "coach/conversation/" +
          paper.id +
          "?conversation_id=" +
          encodeURIComponent(c.id),
      );
      if (alive.current) {
        setSnapshot(next);
        setChosen(c.id);
        atBottom.current = true;
      }
    } catch (e) {
      if (alive.current) setError(String(e));
    } finally {
      if (alive.current) setConnecting(false);
    }
  }
  const currentModel = status?.models?.find(
    (m: any) => m.model === (model || status.model),
  );
  const notesSaved = new Set((context.notes || []).map((n: Row) => n.id));
  const learning = Object.entries(
    context.session?.[0]?.support_evidence || {},
  ) as [string, any][];
  const abilities: Record<string, string> = {
    contribution: "贡献判断",
    mechanism: "机制解释",
    evidence: "证据解读",
    test: "检验设计",
    comparison: "文献比较",
  };
  const assistance: Record<string, string> = {
    model: "示范后作答",
    guided: "共同完成",
    "prompt-only": "提示后作答",
    independent: "本次独立作答",
  };
  const flow = snapshot.reading_flow;
  const flowDone = flow?.status === "completed";
  const flowStarted = flow?.status === "active";
  const stepNumber = `${(flow?.steps || []).findIndex((s: any) => s.id === flow?.current) + 1}/${flow?.steps?.length || 8}`;
  const unavailable =
    status?.state !== "ready" ||
    snapshot.busy ||
    pending ||
    connecting ||
    sending;
  const statusLabel =
    status?.state === "ready"
      ? "已连接"
      : status?.state === "login_required"
        ? "需要登录"
        : status?.state === "unavailable"
          ? "未连接"
          : "连接中";
  const reconnect = async () => {
    try {
      setStatus(await api("coach/reconnect", {}));
    } catch (e) {
      setError(String(e));
    }
  };
  const sessionTools = (
    <>
      <div className="coach-session-row">
        <select
          title="仅列出这篇论文的阅读对话"
          aria-label="当前阅读对话"
          value={snapshot.conversation_id}
          disabled={snapshot.busy || pending || connecting || sending}
          onChange={(e) => void chooseConversation(e.target.value)}
        >
          {!snapshot.conversations.length && (
            <option value="">从新对话开始</option>
          )}
          {snapshot.conversations.map((c, index: number) => (
            <option key={c.id} value={c.id}>
              {c.title} ·{" "}
              {new Date(c.created_at).toLocaleString(undefined, {
                month: "numeric",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })}{" "}
              · #{index + 1}
            </option>
          ))}
        </select>
      </div>
    </>
  );
  const mainline = (
    <div className="coach-mainline" aria-label="论文跟读主线">
      <ol className="coach-progress-track" aria-hidden="true">
        {(flow?.steps || []).map((step: any) => (
          <li
            key={step.id}
            title={step.label}
            className={
              flow?.completed?.some((c: any) => c.step === step.id)
                ? "done"
                : flowStarted && flow?.current === step.id
                  ? "current"
                  : ""
            }
          />
        ))}
      </ol>
      <div className="coach-mainline-heading">
        <strong>
          {flowDone
            ? "本轮跟读已完成"
            : flowStarted
              ? `第 ${stepNumber} 步 · ${flow.label}`
              : "这篇论文的跟读主线"}
        </strong>
        <span title="核查进度不是掌握度">
          已核查 {flow?.completed?.length || 0} / {flow?.steps?.length || 8}
        </span>
      </div>
      <p>
        {flowDone
          ? "回到复习队列巩固理解，也可以继续讨论新问题。"
          : flowStarted
            ? flow?.return_action || flow?.goal
            : "八步：目标 → 贡献 → 设定 → 机制 → 证据 → 边界 → 启发 → 回忆。读到任何地方都可以选中原文插话，主线会停在原处等你。"}
      </p>
      {flow?.pending_question && (
        <p className="coach-pending-question">
          <b>当前问题：</b>
          {flow.pending_question}
        </p>
      )}
      {flow?.needs_recheck && <p>PDF 已换版，主线会从新版本重新核查。</p>}
      <button
        className="primary"
        disabled={unavailable}
        onClick={() =>
          void send(text, false, text.trim() ? "answer" : "follow")
        }
      >
        {text.trim()
          ? "回答并继续主线"
          : flowDone
            ? "回顾阅读总结"
            : flowStarted
              ? "继续主线"
              : "开始跟读"}
      </button>
      <details>
        <summary>查看八步路线与核查依据</summary>
        <p>
          这是核查记录，不是掌握度。独立理解需通过不看答案的回忆与迁移来检验。
        </p>
        <ol>
          {(flow?.steps || []).map((step: any) => {
            const receipt = flow?.completed?.find(
              (c: any) => c.step === step.id,
            );
            return (
              <li
                key={step.id}
                aria-current={
                  !flowDone && flow?.current === step.id ? "step" : undefined
                }
              >
                {receipt ? "✓ " : ""}
                {step.label}
                {receipt && (
                  <details className="reading-receipt">
                    <summary>核查依据</summary>
                    <p>{receipt.evidence}</p>
                    {flow.source_version === paper.source_version &&
                      Number.isInteger(receipt.page_index) &&
                      receipt.page_index >= 0 &&
                      receipt.page_index < paper.page_count && (
                        <button
                          onClick={() =>
                            onLocate(anchorFor(paper, receipt.page_index))
                          }
                        >
                          查看 PDF 第 {receipt.page_index + 1} 页
                        </button>
                      )}
                  </details>
                )}
              </li>
            );
          })}
        </ol>
      </details>
    </div>
  );
  const learningSummary = (
    <>
      {!!learning.length && (
        <details className="coach-learning">
          <summary>本次学习表现 · {learning.length} 项</summary>
          <p className="small muted">
            根据实际回答记录，供下次调整帮助；单次表现不等于已掌握。
          </p>
          {learning.map(([ability, observation]) => (
            <article key={ability}>
              <b>
                {abilities[ability] || ability} ·{" "}
                {assistance[observation.assistance]} ·{" "}
                {
                  {
                    supported: "有证据支持",
                    partial: "还需补充",
                    revise: "需要修正",
                  }[observation.judgment as "supported" | "partial" | "revise"]
                }
              </b>
              <blockquote>{observation.answer_quote}</blockquote>
              <p>{observation.feedback}</p>
              <details>
                <summary>判断依据</summary>
                <p>{observation.criterion}</p>
              </details>
              <button
                disabled={
                  observation.anchor.source_version !== paper.source_version
                }
                onClick={() => onLocate(observation.anchor)}
              >
                {observation.anchor.source_version === paper.source_version
                  ? "核对原文证据"
                  : "旧版本依据，需重新核实"}
              </button>
              <button
                disabled={snapshot.busy || pending || connecting || sending}
                onClick={() =>
                  void chooseConversation(observation.conversation_id)
                }
              >
                查看回答所在对话
              </button>
            </article>
          ))}
        </details>
      )}
    </>
  );
  const turnControls = (
    <>
      <div className="coach-turn-controls">
        <label>
          本轮意图
          <select
            aria-label="本轮意图"
            value={intentChoice}
            onChange={(e) => setIntentChoice(e.target.value as IntentChoice)}
          >
            <option value="auto">
              自动 · {effectiveIntent === "answer" ? "回答主线" : "插话讨论"}
            </option>
            <option value="answer">回答主线</option>
            <option value="detour">插话讨论 · 保留返回点</option>
          </select>
        </label>
        <label>
          帮助方式
          <select
            aria-label="帮助方式"
            value={helpMode}
            onChange={(e) => setHelpMode(e.target.value as HelpMode)}
          >
            {Object.entries(helpLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </div>
      {!canAttachImage && anchor && (
        <p className="small muted">
          选区不在当前可附图位置；文字仍使用选区页。点击选区标签返回后再附图。
        </p>
      )}
      <label className="coach-image-check">
        <input
          type="checkbox"
          checked={includeImage}
          disabled={!canAttachImage}
          onChange={(e) => setIncludeImage(e.target.checked)}
        />
        同时发送当前整页图像（不只是选区）
      </label>
    </>
  );
  const coachSettings = (
    <>
      <details className="coach-options">
        <summary>阅读设置与连接</summary>
        <div className="coach-connection">
          <span
            className={
              "status-dot " + (status?.state === "ready" ? "online" : "")
            }
          />
          <span>{status?.message || "正在连接本机 CLI…"}</span>
          <button
            aria-label="重新连接 CLI"
            title="重新连接 CLI"
            disabled={snapshot.busy}
            onClick={() => void reconnect()}
          >
            <RefreshCw size={13} />
          </button>
        </div>
        <div className="coach-skill">
          paper-research-coach ·{" "}
          {status?.skill_loaded
            ? "阅读规则已就绪，按需查询资料"
            : "正在检查 skill"}
        </div>

        <label>
          模型
          <select
            aria-label="教练模型"
            value={model}
            onChange={(e) => {
              setModel(e.target.value);
              setEffort("");
              localStorage.setItem("prc-coach-model", e.target.value);
              localStorage.removeItem("prc-coach-effort");
            }}
          >
            <option value="">沿用 CLI 配置</option>
            {status?.models?.map((m: any) => (
              <option key={m.model} value={m.model}>
                {m.displayName || m.model}
              </option>
            ))}
          </select>
        </label>
        <label>
          思考深度
          <select
            aria-label="教练思考深度"
            value={effort}
            onChange={(e) => {
              setEffort(e.target.value);
              localStorage.setItem("prc-coach-effort", e.target.value);
            }}
          >
            <option value="">沿用 CLI 配置</option>
            {currentModel?.supportedReasoningEfforts?.map((r: any) => (
              <option key={r.reasoningEffort} value={r.reasoningEffort}>
                {r.reasoningEffort}
              </option>
            ))}
          </select>
        </label>
        <label className="check-label">
          <input
            type="checkbox"
            checked={!!context.session?.[0]?.note_consent}
            onChange={async (e) => {
              try {
                const s = context.session[0];
                await api("commit", {
                  mutations: [
                    {
                      kind: "session",
                      data: { ...s, note_consent: e.target.checked },
                      expected_revision: s.revision,
                    },
                  ],
                });
                refresh();
              } catch (err) {
                setError(String(err));
              }
            }}
          />
          同时把我的对话原话保存为阅读笔记
        </label>
        <p>对话记录始终保留；此选项控制是否额外生成原话笔记。</p>
        <label className="check-label">
          <input
            type="checkbox"
            checked={!!context.session?.[0]?.learning_consent}
            onChange={async (e) => {
              try {
                const s = context.session[0];
                await api("commit", {
                  mutations: [
                    {
                      kind: "session",
                      data: { ...s, learning_consent: e.target.checked },
                      expected_revision: s.revision,
                    },
                  ],
                });
                refresh();
              } catch (err) {
                setError(String(err));
              }
            }}
          />
          记录实际回答与学习反馈，帮助下次调整讲解
        </label>
        <p>
          可随时关闭。按具体能力保存最近一次表现，原始回答和历史反馈保留在本机。
        </p>
        <p>
          笔记和断点存于本机。发送时，当前论文的上下文、对话和所选页面会交给 CLI
          配置的模型提供方；附图会发送整页。Zotero 同步是另一项独立操作。
        </p>
      </details>
    </>
  );
  return (
    <section
      className={"coach-panel " + (expanded ? "expanded" : "")}
      aria-label="论文教练对话"
    >
      <div className="coach-heading">
        <div>
          <MessageCircle size={17} />
          <strong>一起读这篇论文</strong>
          <span
            className="coach-ready"
            title={
              status?.skill_loaded
                ? "本机教练已连接，沿用这篇论文的持久会话"
                : "正在连接"
            }
          >
            <span
              className={
                "status-dot " + (status?.state === "ready" ? "online" : "")
              }
            />
            {statusLabel}
          </span>
        </div>
        <button
          aria-label={
            onOpenTools
              ? "教练设置"
              : expanded
                ? "收起教练对话"
                : "展开教练对话"
          }
          title={
            onOpenTools
              ? "教练设置"
              : expanded
                ? "收起教练对话"
                : "展开教练对话"
          }
          onClick={() => (onOpenTools ? onOpenTools() : setExpanded(!expanded))}
        >
          {expanded ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
        </button>
      </div>
      {status?.state === "login_required" && (
        <div className="coach-login">
          <p>沿用 Codex 登录后，即可在这里带读。</p>
          <button
            onClick={async () => {
              try {
                const r = await api("coach/login", {});
                window.open(r.authUrl, "_blank", "noopener,noreferrer");
              } catch (e) {
                setError(String(e));
              }
            }}
          >
            登录 Codex
          </button>
        </div>
      )}
      {toolsContainer ? (
        createPortal(
          <div className="coach-tools-content">{sessionTools}</div>,
          toolsContainer,
        )
      ) : (
        <details className="coach-fallback-tools">
          <summary>阅读工具</summary>
          {sessionTools}
        </details>
      )}
      {mainline}
      <div
        className="coach-messages"
        ref={scroll}
        onScroll={() => {
          const e = scroll.current;
          if (e)
            atBottom.current =
              e.scrollHeight - e.scrollTop - e.clientHeight < 90;
        }}
        role="log"
        aria-label="阅读对话记录"
      >
        {!snapshot.messages.length && (
          <div className="coach-welcome">
            <span className="eyebrow">怎么用</span>
            <h3>一边读原文，一边一步步形成判断</h3>
            <ol className="coach-howto">
              <li>
                点上方<b>开始跟读</b>：教练从“这次要判断什么”开始，每轮只推进一步、只问一个问题。
              </li>
              <li>
                有问题时直接在下方输入你的回答，按 Enter 发送，主线随之前进；想先听讲解，就把“帮助方式”改为直接解释。
              </li>
              <li>
                读到看不懂的地方，选中原文点<b>讨论这处</b>：这是插话，主线停在原步骤，问完点<b>继续主线</b>回来。
              </li>
            </ol>
            <p>也可以不走主线，直接提问。刷新页面后会接着这篇论文的同一段对话。</p>
          </div>
        )}
        {snapshot.messages.map((m, index) => (
          <article key={m.id} className={"coach-message " + m.role}>
            <div className="coach-message-label">
              {m.role === "user"
                ? m.intent === "follow"
                  ? "继续跟读"
                  : "我"
                : "论文教练"}
              {m.imported && <span>来自 CLI 对话</span>}
              {m.role === "user" && m.intent === "answer" && (
                <span>回答主线</span>
              )}
              {m.role === "user" && m.help_mode && m.help_mode !== "guided" && (
                <span>{helpLabels[m.help_mode]}</span>
              )}
              {m.status !== "completed" && (
                <span className={"coach-status " + m.status}>
                  {m.status === "queued"
                    ? "准备回复…"
                    : m.status === "streaming"
                      ? "正在回复…"
                      : m.status === "interrupted"
                        ? "已停止"
                        : m.status === "failed"
                          ? "未完成"
                          : ""}
                </span>
              )}
            </div>
            {m.anchor &&
              !(
                m.role === "assistant" &&
                sameAnchor(snapshot.messages[index - 1]?.anchor, m.anchor)
              ) && (
                <button
                  className={
                    "anchor-label" + (anchorQuote(m.anchor) ? " quoted" : "")
                  }
                  title="回到原文位置"
                  onClick={() => onLocate(m.anchor)}
                >
                  <span>
                    <MapPin size={13} />
                    {location(m.anchor)}
                  </span>
                  {m.role === "user" && anchorQuote(m.anchor) && (
                    <q>{anchorQuote(m.anchor)}</q>
                  )}
                </button>
              )}
            <div className="coach-prose">
              {m.context_scope && (
                <details className="coach-source-scope">
                  <summary>本轮发送范围</summary>
                  <p className="small muted">
                    {m.context_scope.page_index === null
                      ? "无可用 PDF 正文"
                      : `PDF 第 ${m.context_scope.page_index + 1} 页`}
                    、阅读断点，以及 {m.context_scope.notes_included} /{" "}
                    {m.context_scope.notes_total}{" "}
                    条笔记的节选。教练可按需回查这篇论文的其他记录；本机原文保持完整。
                  </p>
                </details>
              )}
              {m.connection_notice && (
                <p className="small muted">{m.connection_notice}</p>
              )}
              {m.role === "user" ? (
                <p className="verbatim">{m.content}</p>
              ) : (
                <Markdown
                  remarkPlugins={[remarkGfm, remarkCjkFriendly, remarkMath]}
                  rehypePlugins={[rehypeKatex]}
                  components={{
                    a: (props) => (
                      <a {...props} target="_blank" rel="noopener noreferrer" />
                    ),
                  }}
                >
                  {prose(m.content)}
                </Markdown>
              )}
              {!m.content && m.status === "streaming" && (
                <span className="coach-thinking">正在核对论文与阅读记录…</span>
              )}
            </div>
            {m.error && <p className="coach-error">{m.error}</p>}
            {m.actions?.length ? (
              <div className="coach-actions">
                {m.actions
                  .filter(
                    (a, i, all) =>
                      all.findIndex(
                        (b) => b.id === a.id && b.label === a.label,
                      ) === i,
                  )
                  .map((a) =>
                    a.kind === "session" ? (
                      <span className="coach-saved-action" key={a.id + a.label}>
                        {a.label}
                      </span>
                    ) : (
                      <button
                        key={a.id + a.label}
                        onClick={() => {
                          refresh();
                          if (a.anchor) onLocate(a.anchor);
                          else onAction(a.kind);
                        }}
                      >
                        {a.label}
                      </button>
                    ),
                  )}
              </div>
            ) : null}
            {m.content && m.status !== "streaming" && m.intent !== "follow" && (
              <button
                className="text-button small"
                disabled={notesSaved.has("chat-" + m.id)}
                onClick={async () => {
                  try {
                    await api(
                      "coach/save-message/" +
                        snapshot.conversation_id +
                        "/" +
                        m.id,
                      {},
                    );
                    refresh();
                    report(
                      m.role === "user"
                        ? "原话已保存为笔记"
                        : "已保存为独立 AI 评论",
                    );
                  } catch (e) {
                    setError(String(e));
                  }
                }}
              >
                {notesSaved.has("chat-" + m.id)
                  ? "已在笔记中"
                  : m.role === "user"
                    ? "保留为原话笔记"
                    : "保存 AI 评论"}
              </button>
            )}
          </article>
        ))}
      </div>
      <div className="coach-compose">
        {toolsContainer ? (
          createPortal(<div>{learningSummary}</div>, toolsContainer)
        ) : (
          <>{learningSummary}</>
        )}
        {status?.state === "unavailable" && (
          <div className="coach-offline" role="status">
            <p>
              <b>AI 带读暂未连接。</b>
              需要本机已安装并登录的 Codex CLI；阅读、标注和笔记照常可用。
            </p>
            <button disabled={snapshot.busy} onClick={() => void reconnect()}>
              <RefreshCw size={13} />
              重新连接
            </button>
          </div>
        )}
        {error && (
          <div className="coach-error" role="alert">
            {error}
            <button aria-label="关闭对话提示" onClick={() => setError("")}>
              <X size={13} />
            </button>
          </div>
        )}
        {pending && (
          <button
            className="coach-retry"
            disabled={sending || snapshot.busy}
            onClick={() => void send("", true)}
          >
            确认上次发送 · 使用相同编号恢复
          </button>
        )}
        <div className="coach-context-chips" hidden={!anchor}>
          <span>PDF 第 {(anchor?.page_index ?? page) + 1} 页</span>
          {anchor && (
            <div>
              <button className="anchor-label" onClick={() => onLocate(anchor)}>
                <MapPin size={12} />
                {anchorQuote(anchor) ? "已附上选中文字" : "已附上选区"}
              </button>
              <button aria-label="移除对话选区" onClick={onClearAnchor}>
                <X size={12} />
              </button>
            </div>
          )}
        </div>
        {anchorQuote(anchor) && (
          <blockquote className="coach-selection">
            {anchorQuote(anchor)}
          </blockquote>
        )}
        {turnControls}
        {snapshot.read_only && (
          <button
            onClick={() =>
              void chooseConversation(snapshot.canonical_conversation_id || "")
            }
          >
            历史对话为只读 · 返回当前对话
          </button>
        )}
        <textarea
          disabled={!!snapshot.read_only}
          aria-label="发给论文教练的消息"
          placeholder={
            effectiveIntent === "answer"
              ? "写下你的判断、理由或仍不确定的地方…"
              : "写下问题或反驳；这次讨论会保留主线返回点…"
          }
          ref={composer}
          rows={2}
          value={text}
          onChange={(e) => change(e.target.value)}
          onKeyDown={(e) => {
            // Enter sends, Shift+Enter breaks a line; IME confirmation never sends.
            if (
              e.key === "Enter" &&
              !e.shiftKey &&
              !e.altKey &&
              !e.nativeEvent.isComposing &&
              e.nativeEvent.keyCode !== 229
            ) {
              e.preventDefault();
              void send();
            }
          }}
        />
        <div className="coach-compose-footer">
          <span>Enter 发送 · Shift + Enter 换行</span>
          {snapshot.busy ? (
            <button
              className="coach-stop"
              onClick={async () => {
                try {
                  await api("coach/stop/" + snapshot.conversation_id, {});
                } catch (e) {
                  setError(String(e));
                }
              }}
            >
              <Square size={13} />
              停止
            </button>
          ) : (
            <button
              className="primary"
              aria-label="发送给论文教练"
              disabled={
                sending ||
                connecting ||
                snapshot.read_only ||
                !text.trim() ||
                status?.state !== "ready" ||
                pending
              }
              onClick={() => void send()}
            >
              <ArrowUp size={17} />
            </button>
          )}
        </div>
        {toolsContainer ? (
          createPortal(
            <div className="coach-tools-content">{coachSettings}</div>,
            toolsContainer,
          )
        ) : (
          <>{coachSettings}</>
        )}
        {!!context.pending_thoughts?.length && (
          <button
            className="coach-discuss"
            disabled={snapshot.busy || status?.state !== "ready" || pending}
            onClick={() =>
              void send(
                "请讨论我已保存但尚未讨论的笔记，引用我的原话，保留独立的 AI 评论。一次先讨论最关键的一条。",
                false,
                "detour",
              )
            }
          >
            讨论待讨论笔记 · {context.pending_thoughts.length}
          </button>
        )}
        {anchor && (
          <button
            className="coach-discuss"
            disabled={snapshot.busy || status?.state !== "ready" || pending}
            onClick={() =>
              void send(
                "请解释当前选区，先说明它在论文论证里解决什么问题，再帮我检验一个关键判断。",
                false,
                "detour",
              )
            }
          >
            讨论当前选区
          </button>
        )}
      </div>
    </section>
  );
}

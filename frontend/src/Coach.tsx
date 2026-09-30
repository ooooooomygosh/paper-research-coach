import { useEffect, useRef, useState } from "react";
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
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { api, ApiError, id, location, type Row } from "./api";

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
};
type Snapshot = {
  conversation_id: string;
  conversations: Row[];
  messages: Message[];
  busy: boolean;
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
  const scroll = useRef<HTMLDivElement>(null);
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
    if (anchor?.rects?.length && !anchor?.quote) setIncludeImage(true);
  }, [anchor]);
  function change(value: string) {
    setText(value);
    localStorage.setItem(key, value);
  }
  function pageImage() {
    const canvas = document.querySelector<HTMLCanvasElement>(
      `.pdf-page[data-paper-id="${paper.id}"][data-page-index="${page}"] canvas`,
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
  async function send(content = text, retry = false, intent = "detour") {
    if (sending || connecting || snapshot.busy || (!retry && intent !== "follow" && !content.trim()))
      return;
    if (pending && !retry) {
      setError("上次发送的结果还未确认。先点击确认上次发送，可避免重复提问。");
      return;
    }
    let body: any;
    try {
      body = retry
        ? JSON.parse(localStorage.getItem(jobKey) || "null")
        : {
            operation_id: id(),
            conversation_id: snapshot.conversation_id,
            content,
            intent,
            anchor: intent === "follow" ? null : anchor,
            page_index: page,
            source_version: paper.source_version,
            model,
            effort,
            page_image: includeImage ? pageImage() : "",
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
      await api("coach/active", { paper_id: paper.id, conversation_id: c.id });
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
  const flow = snapshot.reading_flow;
  const flowDone = flow?.status === "completed";
  const flowStarted = flow?.status === "active";
  const unavailable = status?.state !== "ready" || snapshot.busy || pending || connecting || sending;
  return (
    <section
      className={"coach-panel " + (expanded ? "expanded" : "")}
      aria-label="论文教练对话"
    >
      <div className="coach-heading">
        <div>
          <MessageCircle size={17} />
          <strong>一起读这篇论文</strong>
          <span className="coach-ready" title={status?.skill_loaded ? "本机教练已连接，每轮加载 paper-research-coach" : "正在连接"}><span className={"status-dot " + (status?.state === "ready" ? "online" : "")} />{status?.state === "ready" ? "已连接" : "连接中"}</span>
        </div>
        <button
          aria-label={expanded ? "收起教练对话" : "展开教练对话"}
          title={expanded ? "收起教练对话" : "展开教练对话"}
          onClick={() => setExpanded(!expanded)}
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
          {snapshot.conversations.map((c, index) => (
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
        <button
          className="text-button"
          aria-label="新建阅读对话"
          onClick={() => void chooseConversation("", true)}
          disabled={snapshot.busy || pending || connecting || sending}
        >
          <Plus size={14} />
          新对话
        </button>
      </div>
      <div className="coach-mainline" aria-label="论文跟读主线">
        <div className="coach-mainline-heading">
          <strong>{flowDone ? "本轮跟读已完成" : flowStarted ? flow.label : "这篇论文的跟读主线"}</strong>
          <span>{flow?.completed?.length || 0} / 8</span>
        </div>
        <p>{flowDone ? "回到复习队列巩固理解，也可以继续讨论新问题。" : flow?.return_action || flow?.goal || "从阅读目标到证据、研究启发和复习，按既定流程一起读。"}</p>
        {flow?.needs_recheck && <p>PDF 已换版，主线会从新版本重新核查。</p>}
        <button className="primary" disabled={unavailable}
          onClick={() => void send(text, false, text.trim() ? "answer" : "follow")}>
          {text.trim() ? "回答并继续主线" : flowDone ? "回顾阅读总结" : flowStarted ? "继续主线" : "开始跟读"}
        </button>
        <details>
          <summary>查看阅读路线</summary>
          <ol>{(flow?.steps || []).map((step: any, index: number) => (
            <li key={step.id} aria-current={!flowDone && flow?.current === step.id ? "step" : undefined}>
              {index < (flow?.completed?.length || 0) ? "✓ " : ""}{step.label}
            </li>
          ))}</ol>
        </details>
      </div>
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
            <span className="eyebrow">每篇论文都有自己的阅读路线</span>
            <h3>论文在左边，思考在这里。</h3>
            <p>
              点“开始跟读”即可按 Skill 的完整流程阅读。随时提问或讨论选区，回答后会回到主线；新对话沿用这篇论文的阅读进度。
            </p>
          </div>
        )}
        {snapshot.messages.map((m) => (
          <article key={m.id} className={"coach-message " + m.role}>
            <div className="coach-message-label">
              {m.role === "user" ? m.intent === "follow" ? "继续跟读" : "我" : "论文教练"}
              {m.imported && <span>来自 CLI 对话</span>}
              <span>
                {m.status === "queued"
                  ? "准备回复…"
                  : m.status === "streaming"
                    ? "正在回复…"
                    : m.status === "interrupted"
                      ? "已停止"
                      : m.status === "failed"
                        ? "未完成"
                        : "已保存"}
              </span>
            </div>
            {m.anchor && (
              <button
                className="anchor-label"
                onClick={() => onLocate(m.anchor)}
              >
                <MapPin size={13} />
                {location(m.anchor)}
              </button>
            )}
            <div className="coach-prose">
              {m.connection_notice && (
                <p className="small muted">{m.connection_notice}</p>
              )}
              {m.role === "user" ? (
                <p className="verbatim">{m.content}</p>
              ) : (
                <Markdown
                  remarkPlugins={[remarkGfm, remarkMath]}
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
                {m.actions.filter((a, i, all) => all.findIndex(b => b.id === a.id && b.label === a.label) === i).map((a) => a.kind === "session" ? (
                  <span className="coach-saved-action" key={a.id + a.label}>{a.label}</span>
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
                ))}
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
        <div className="coach-context-chips">
          <span>PDF 第 {page + 1} 页 · 自动带入阅读断点</span>
          {anchor && (
            <div>
              <button className="anchor-label" onClick={() => onLocate(anchor)}>
                <MapPin size={12} />
                {anchor.quote ? "已附上选中文字" : "已附上选区"}
              </button>
              <button aria-label="移除对话选区" onClick={onClearAnchor}>
                <X size={12} />
              </button>
            </div>
          )}
        </div>
        {anchor?.quote && (
          <blockquote className="coach-selection">{anchor.quote}</blockquote>
        )}
        <label className="coach-image-check">
          <input
            type="checkbox"
            checked={includeImage}
            onChange={(e) => setIncludeImage(e.target.checked)}
          />
          同时查看当前页图表
        </label>
        <textarea
          aria-label="发给论文教练的消息"
          placeholder="随时插话提问；回答主线问题后，点“回答并继续主线”…"
          value={text}
          onChange={(e) => change(e.target.value)}
          onKeyDown={(e) => {
            if (
              (e.ctrlKey || e.metaKey) &&
              e.key === "Enter" &&
              !e.nativeEvent.isComposing
            ) {
              e.preventDefault();
              void send();
            }
          }}
        />
        <div className="coach-compose-footer">
          <span>随时插话 · 回答后回到主线</span>
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
          onClick={async () => {
            try {
              setStatus(await api("coach/reconnect", {}));
            } catch (e) {
              setError(String(e));
            }
          }}
        >
          <RefreshCw size={13} />
        </button>
      </div>
      <div className="coach-skill">
        paper-research-coach ·{" "}
        {status?.skill_loaded ? "skill 已就绪，每轮显式加载" : "正在检查 skill"}
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
        </details>
        {!!context.pending_thoughts?.length && (
          <button
            className="coach-discuss"
            disabled={snapshot.busy || status?.state !== "ready" || pending}
            onClick={() =>
              void send(
                "请讨论我已保存但尚未讨论的笔记，引用我的原话，保留独立的 AI 评论。一次先讨论最关键的一条。",
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

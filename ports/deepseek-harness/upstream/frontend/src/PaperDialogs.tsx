import { useState } from "react";
import { ArrowRight, BookOpen, X } from "lucide-react";
import { api, put, type Row } from "./api";
import Dialog from "./Dialog";

export function PaperEditor({
  paper,
  onClose,
  onDone,
  report,
}: {
  paper: Row;
  onClose: () => void;
  onDone: () => void | Promise<void>;
  report: (s: string) => void;
}) {
  const [value, setValue] = useState(paper),
    [file, setFile] = useState<File | null>(null),
    [path, setPath] = useState(paper.source_path || ""),
    [busy, setBusy] = useState(false);
  return (
    <Dialog label="论文信息与版本" onClose={onClose} canClose={!busy}>
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
                value={value[k] || ""}
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
            setBusy(true);
            try {
              await put("paper", value);
              await onDone();
            } catch (e) {
              report(String(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? "正在保存…" : "保存信息"}
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
                await onDone();
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
          <button disabled={busy} onClick={onClose}>关闭</button>
        </div>
    </Dialog>
  );
}
export function ImportModal({
  onClose,
  onDone,
  report,
}: {
  onClose: () => void;
  onDone: (p: Row) => void | Promise<void>;
  report: (s: string) => void;
}) {
  const [title, setTitle] = useState(""),
    [path, setPath] = useState(""),
    [goal, setGoal] = useState(""),
    [file, setFile] = useState<File | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [dragging, setDragging] = useState(false);
  function chooseFile(f: File | null) {
    if (!f) return;
    if (!/\.pdf$/i.test(f.name) && f.type !== "application/pdf") {
      setError("请选择 PDF 文件；其他格式不会被导入。");
      return;
    }
    setError("");
    setFile(f);
    setPath("");
    if (!title.trim() || title === file?.name.replace(/\.pdf$/i, ""))
      setTitle(f.name.replace(/\.pdf$/i, ""));
  }
  async function submit() {
    if (busy) return;
    setError("");
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
      await onDone(p);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog label="打开一篇论文" onClose={onClose} canClose={!busy}>
        <div className="panel-title">
          <h2>打开一篇论文</h2>
          <button aria-label="关闭导入" disabled={busy} onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        <p className="muted small">先打开原文，再决定需要多少帮助。标题和阅读目标都可以稍后修改。</p>
        <label className={"file-drop" + (dragging ? " dragging" : "")}
          onDragOver={(e) => { e.preventDefault(); if (!busy) setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            if (!busy) {
              if (e.dataTransfer.files.length !== 1) setError("一次打开一篇 PDF，其他论文可以稍后导入。");
              else chooseFile(e.dataTransfer.files[0]);
            }
          }}
        >
          <BookOpen size={26} />
          <span>{file ? file.name : "选择或拖入一篇 PDF"}</span>
          <input
            type="file"
            accept="application/pdf,.pdf"
            disabled={busy}
            onChange={(e) => {
              chooseFile(e.target.files?.[0] || null);
              e.target.value = "";
            }}
          />
        </label>
        <label>
          论文名称
          <input value={title} onChange={(e) => setTitle(e.target.value)} />
        </label>
        <label>
          这次阅读为了什么？（可选）
          <textarea
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder="例如：判断这个方法是否适合我的问题"
          />
        </label>
        <details>
          <summary>或连接本地路径 / 只记书目信息</summary>
          <input aria-label="已有 PDF 的本地路径"
            placeholder="/path/to/paper.pdf"
            value={path}
            onChange={(e) => { setPath(e.target.value); if (e.target.value) setFile(null); }}
          />
          <p className="small muted">
            只建立只读连接。也可以不填路径，先保存论文书目。
          </p>
        </details>
        {error && <p role="alert" className="form-error">{error}</p>}
        <p className="small muted">PDF 与笔记保存在本机。使用 AI 时，相关内容会发往你选择的模型服务。</p>
        <button
          className="primary"
          disabled={busy || !title.trim()}
          onClick={submit}
        >
          {busy
            ? "正在导入…"
            : file || path.trim() || !title.trim()
              ? "打开论文"
              : "保存书目信息"}
          <ArrowRight size={16} />
        </button>
    </Dialog>
  );
}

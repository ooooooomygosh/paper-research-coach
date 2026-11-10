import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";

export type UpdateInfo = {
  current: string;
  available: boolean;
  latest?: string;
  notes_url?: string;
  disabled?: boolean;
  managed_by?: string;
  /** Verified new versions install in the background (the restart waits until nobody reads). */
  auto?: boolean;
  job?: { state: string; message: string; version?: string };
};
const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

// One quiet answer to "is there a newer version?", shared by every place that mentions it.
// The server checks GitHub at most once a day; nothing here interrupts reading.
export function useUpdate(ready: boolean) {
  const [info, setInfo] = useState<UpdateInfo | null>(null);
  const [phase, setPhase] = useState<"" | "working" | "restarting" | "error" | "done">("");
  const [message, setMessage] = useState("");
  const running = useRef(false);

  useEffect(() => {
    if (!ready) return;
    let disposed = false;
    api("update")
      .then((s) => !disposed && setInfo(s))
      .catch(() => {});
    return () => {
      disposed = true;
    };
  }, [ready]);

  const apply = useCallback(async () => {
    if (running.current || !info) return;
    running.current = true;
    setPhase("working");
    setMessage("正在下载并安装新版本…");
    try {
      await api("update/apply", {});
      const started = Date.now();
      while (Date.now() - started < 180000) {
        await wait(1500);
        try {
          const s: UpdateInfo = await api("update");
          if (s.current !== info.current) {
            // The restarted service already runs the new version: load its page.
            window.location.reload();
            return;
          }
          if (s.job?.state === "error") {
            setPhase("error");
            setMessage(s.job.message);
            return;
          }
          if (s.job?.state === "done") {
            setPhase("done");
            setMessage(s.job.message);
            return;
          }
          if (s.job?.state === "restarting") {
            setPhase("restarting");
            setMessage(s.job.message);
          }
        } catch {
          // The service is restarting; keep asking until it answers again.
          setPhase("restarting");
          setMessage("正在重新启动…");
        }
      }
      setPhase("error");
      setMessage("等待时间过长。请在终端运行 prc 重新打开。");
    } catch (e) {
      setPhase("error");
      setMessage(e instanceof Error ? e.message : String(e));
    } finally {
      running.current = false;
    }
  }, [info]);

  const setAuto = useCallback(async (auto: boolean) => {
    try {
      const r = await api("update/settings", { auto });
      setInfo((i) => (i ? { ...i, auto: r.auto } : i));
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    }
  }, []);

  return { info, phase, message, apply, setAuto, available: !!info?.available && !info.disabled };
}
export type UpdateState = ReturnType<typeof useUpdate>;

export function UpdateRow({ update, variant = "row" }: { update: UpdateState; variant?: "row" | "banner" }) {
  const [dismissedNow, setDismissedNow] = useState(false);
  let stored: string | null = null;
  try {
    stored = localStorage.getItem("prc-update-dismissed");
  } catch {}
  if (!update.available || dismissedNow || (variant === "banner" && !!stored && stored === update.info?.latest)) return null;
  const busy = update.phase === "working" || update.phase === "restarting";
  // Installed in the background already: only a short reload is left.
  const ready = update.info?.job?.state === "ready";
  return (
    <div className={"update-row " + variant} role="status">
      <span>
        新版本 <b>{update.info?.latest}</b> {ready ? "已装好" : "可用"}
      </span>
      <button className={variant === "banner" ? "primary" : ""} disabled={busy || update.phase === "done"} onClick={() => void update.apply()}>
        {busy ? "正在更新…" : update.phase === "error" ? "重试更新" : ready ? "重新载入（约 5 秒）" : "更新并重启"}
      </button>
      {update.info?.notes_url && (
        <a href={update.info.notes_url} target="_blank" rel="noopener noreferrer">
          更新内容
        </a>
      )}
      {variant === "banner" && !busy && (
        <button
          className="text-button"
          onClick={() => {
            try {
              localStorage.setItem("prc-update-dismissed", update.info?.latest || "");
            } catch {}
            setDismissedNow(true);
          }}
        >
          稍后
        </button>
      )}
      {update.message && <small className={update.phase === "error" ? "error" : ""}>{update.message}</small>}
    </div>
  );
}

/** Settings: the version that runs, and whether new versions install by themselves. */
export function UpdateSettings({ update }: { update: UpdateState }) {
  const info = update.info;
  if (!info) return null;
  if (info.managed_by) return <PluginUpdateSettings kernelVersion={info.current} />;
  return (
    <div className="update-settings">
      <p>
        当前版本 <b>{info.current}</b>
        {info.available ? <> · 新版本 <b>{info.latest}</b> {info.job?.state === "ready" ? "已装好" : "可用"}</> : " · 已是最新"}
      </p>
      <label>
        <input type="checkbox" checked={!!info.auto} disabled={info.disabled} onChange={(e) => void update.setAuto(e.target.checked)} />
        自动安装新版本（先校验，再在后台安装；没人阅读时才重启，Skill 副本随之更新）
      </label>
      {info.disabled && <small>已用环境变量 PRC_NO_UPDATE_CHECK 关闭更新检查。</small>}
      <UpdateRow update={update} />
    </div>
  );
}


type PluginUpdateInfo = {
  current_version: string;
  state: "idle" | "checking" | "downloading" | "staged" | "installing" | "applied" | "error" | "rolled_back" | "unsupported";
  staged_version: string | null;
  available: boolean;
  auto: boolean;
  message: string;
  error?: string;
};

/** DSH packages are verified and staged by the host, never installed as wheels. */
export function PluginUpdateSettings({ kernelVersion }: { kernelVersion?: string }) {
  const [status, setStatus] = useState<PluginUpdateInfo | null>(null);
  const [error, setError] = useState("");
  const checking = useRef(false);
  useEffect(() => {
    let disposed = false;
    const read = async () => {
      try { const value = await api("plugin-update"); if (!disposed) { setStatus(value); setError(""); } }
      catch (e) { if (!disposed) setError(e instanceof Error ? e.message : "插件版本信息暂不可用。"); }
    };
    void read();
    const timer = window.setInterval(() => void read(), 3000);
    return () => { disposed = true; window.clearInterval(timer); };
  }, []);
  const busy = checking.current || ["checking", "downloading", "installing"].includes(status?.state || "");
  async function check() {
    if (checking.current) return;
    checking.current = true;
    setError("");
    try { setStatus(await api("plugin-update/check", {})); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { checking.current = false; }
  }
  return <div className="update-settings" aria-label="DSH 插件版本与更新">
    <p>DSH 插件版本 <b>{status?.current_version || "正在读取…"}</b></p>
    {status?.state === "staged" && <p role="status">更新 <b>{status.staged_version}</b> 已准备；下次完全退出 Harness 并重新打开时安装。</p>}
    {status?.message && <p role={status.state === "error" ? "alert" : "status"}>{status.message}</p>}
    <button disabled={busy} onClick={() => void check()}>{busy ? "正在检查或准备更新…" : "检查 DSH 插件更新"}</button>
    <a href="https://github.com/ooooooomygosh/paper-research-coach/releases" target="_blank" rel="noopener noreferrer">版本说明与安装包</a>
    <p><small>macOS Apple silicon 自动检查兼容的 DSH 发布包，校验后暂存；阅读过程中不替换运行中的版本。不支持的平台保持当前版本。</small></p>
    {kernelVersion && <small>工作台内核 {kernelVersion}；插件更新由 Harness 管理，不使用独立工作台安装器。</small>}
    {error && <p role="alert">{error}</p>}
  </div>;
}

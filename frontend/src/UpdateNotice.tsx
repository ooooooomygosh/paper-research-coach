import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";

export type UpdateInfo = {
  current: string;
  available: boolean;
  latest?: string;
  notes_url?: string;
  disabled?: boolean;
  job?: { state: string; message: string };
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

  return { info, phase, message, apply, available: !!info?.available && !info.disabled };
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
  return (
    <div className={"update-row " + variant} role="status">
      <span>
        新版本 <b>{update.info?.latest}</b> 可用
      </span>
      <button className={variant === "banner" ? "primary" : ""} disabled={busy || update.phase === "done"} onClick={() => void update.apply()}>
        {busy ? "正在更新…" : update.phase === "error" ? "重试更新" : "更新并重启"}
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

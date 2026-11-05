import { useState } from "react";
import { Check, Pause, RotateCcw } from "lucide-react";
import { api } from "../api";
import type { Quest } from "./types";

/**
 * The end of a side quest, decided by the reader: "I get it now" (with one sentence in their own
 * words, kept as written) or "set it aside". There is no score; parking a question is not a failure.
 */
export default function QuestControls({ branchId, quest, disabled, onSaved }: {
  branchId: string;
  quest?: Quest;
  disabled?: boolean;
  onSaved: (quest: Quest) => void;
}) {
  const [writing, setWriting] = useState(false);
  const [takeaway, setTakeaway] = useState(quest?.takeaway || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const save = async (status: NonNullable<Quest["status"]>, text = "") => {
    setBusy(true);
    setError("");
    try {
      const result = await api(`coach/branch/${branchId}/quest`, { status, takeaway: text });
      onSaved(result.quest);
      setWriting(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  const status = quest?.status || "open";

  if (status === "done" && !writing)
    return (
      <div className="quest-controls done" data-export="skip" role="group" aria-label="支线任务">
        <p>
          <Check size={15} />
          <b>支线完成：已弄懂</b>
          {quest?.takeaway && <span className="quest-takeaway">我的收获：{quest.takeaway}</span>}
        </p>
        <span className="quest-controls-actions">
          <button type="button" disabled={busy || disabled} onClick={() => setWriting(true)}>改写收获</button>
          <button type="button" disabled={busy || disabled} onClick={() => void save("open")}><RotateCcw size={13} />还没懂，重新打开</button>
        </span>
        {error && <span className="quest-error" role="alert">{error}</span>}
      </div>
    );
  if (status === "parked" && !writing)
    return (
      <div className="quest-controls parked" data-export="skip" role="group" aria-label="支线任务">
        <p><Pause size={14} /><b>这条支线先放一放</b><span>它会留在任务日志里，随时可以回来。</span></p>
        <span className="quest-controls-actions">
          <button type="button" disabled={busy || disabled} onClick={() => void save("open")}>继续这条支线</button>
        </span>
        {error && <span className="quest-error" role="alert">{error}</span>}
      </div>
    );
  return (
    <div className="quest-controls" data-export="skip" role="group" aria-label="支线任务">
      {writing ? (
        <form
          className="quest-takeaway-form"
          onSubmit={(e) => {
            e.preventDefault();
            void save("done", takeaway);
          }}
        >
          <label htmlFor={"quest-" + branchId}>用一句话写下你弄懂了什么（可以不写）</label>
          <textarea
            id={"quest-" + branchId}
            rows={2}
            maxLength={500}
            value={takeaway}
            autoFocus
            placeholder="例如：分数不缩放会随维度变大，softmax 就会饱和。"
            onChange={(e) => setTakeaway(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing && e.nativeEvent.keyCode !== 229) {
                e.preventDefault();
                void save("done", takeaway);
              }
            }}
          />
          <span className="quest-controls-actions">
            <button type="submit" className="primary" disabled={busy || disabled}><Check size={14} />记下，支线完成</button>
            <button type="button" disabled={busy} onClick={() => setWriting(false)}>取消</button>
          </span>
        </form>
      ) : (
        <>
          <p><b>支线任务</b><span>弄懂了就收下这条支线，回到主线继续读。</span></p>
          <span className="quest-controls-actions">
            <button type="button" className="primary" disabled={busy || disabled} onClick={() => setWriting(true)}><Check size={14} />我弄懂了</button>
            <button type="button" disabled={busy || disabled} onClick={() => void save("parked")}><Pause size={13} />先放一放</button>
          </span>
        </>
      )}
      {error && <span className="quest-error" role="alert">{error}</span>}
    </div>
  );
}

import { useState } from "react";
import Dialog from "./Dialog";
import { api } from "./api";

export default function PageOcr({paperId, version, page}: {paperId: string; version: string; page: number}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{text: string; engine: string} | null>(null);
  const [error, setError] = useState("");
  async function read() {
    setOpen(true);
    if (result || busy) return;
    setBusy(true);
    setError("");
    try {
      setResult(await api(`ocr/${paperId}/${page}?version=${encodeURIComponent(version)}`, {}));
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  return <>
    <button onClick={() => void read()}>识别本页文字</button>
    {open && <Dialog label="本页文字识别" onClose={() => setOpen(false)}>
      <h2>第 {page + 1} 页 · 文字识别</h2>
      {busy && <p role="status">正在本机识别…</p>}
      {error && <p role="alert">{error}</p>}
      {result && <><small>{result.engine} · 引用前请与原图核对</small>
        {result.text ? <textarea aria-label="本页识别结果" readOnly value={result.text} rows={12}
          style={{width:"100%", marginBlock:"1em"}} /> : <p>本页未识别出文字。</p>}</>}
      <button onClick={() => setOpen(false)}>关闭</button>
    </Dialog>}
  </>;
}

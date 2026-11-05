import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

/** Keep a page-number draft separate from the persisted, zero-based PDF cursor. */
export default function PageNavigation({ page, count, onChange, labelPrefix = "" }: {
  labelPrefix?: string;
  page: number;
  count: number;
  onChange: (page: number) => void;
}) {
  const [draft, setDraft] = useState(String(page + 1));
  useEffect(() => setDraft(String(page + 1)), [page, count]);
  function commit() {
    const trimmed = draft.trim();
    if (!/^\d+$/.test(trimmed) || count < 1) {
      setDraft(String(page + 1));
      return;
    }
    const next = Math.max(1, Math.min(count, Number(trimmed)));
    setDraft(String(next));
    if (next - 1 !== page) onChange(next - 1);
  }
  return (
    <div className="compact-pages" role="group" aria-label="PDF 翻页">
      <button aria-label={labelPrefix + "上一页"} disabled={page <= 0 || count < 1} onClick={() => onChange(page - 1)}>
        <ChevronLeft size={16} />
      </button>
      <input aria-label="阅读页码" title="输入页码后按 Enter；Esc 取消"
        type="text" inputMode="numeric" pattern="[0-9]*" disabled={count < 1}
        value={draft} onChange={(e) => setDraft(e.target.value)} onBlur={commit}
        onFocus={(e) => e.currentTarget.select()}
        onKeyDown={(e) => {
          if (e.key === "Enter") { e.preventDefault(); commit(); }
          if (e.key === "Escape") {
            e.preventDefault(); e.stopPropagation(); setDraft(String(page + 1));
          }
        }} />
      <span>/ {count}</span>
      <button aria-label={labelPrefix + "下一页"} disabled={count < 1 || page >= count - 1} onClick={() => onChange(page + 1)}>
        <ChevronRight size={16} />
      </button>
    </div>
  );
}

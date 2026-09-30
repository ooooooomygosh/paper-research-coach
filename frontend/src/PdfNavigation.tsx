import { useEffect, useRef, useState } from "react";
import type { PDFDocumentProxy } from "pdfjs-dist";

type OutlineEntry = { title: string; page: number | null; depth: number };
type Hit = { page: number; snippet: string };

export default function PdfNavigation({
  doc,
  sourceKey,
  page,
  onNavigate,
}: {
  doc: PDFDocumentProxy | null;
  sourceKey: string;
  page: number;
  onNavigate: (page: number) => void;
}) {
  const [open, setOpen] = useState(false);
  const [outline, setOutline] = useState<OutlineEntry[]>([]);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<Hit[]>([]);
  const [progress, setProgress] = useState("");
  const [searching, setSearching] = useState(false);
  const [scanned, setScanned] = useState(0);
  const generation = useRef(0);
  const trail = useRef({
    key: sourceKey,
    pages: [page],
    cursor: 0,
    target: null as number | null,
  });
  const [, redraw] = useState(0);

  useEffect(() => {
    const t = trail.current;
    if (t.key !== sourceKey)
      trail.current = {
        key: sourceKey,
        pages: [page],
        cursor: 0,
        target: null,
      };
    else if (t.target === page) t.target = null;
    else if (t.pages[t.cursor] !== page) {
      t.pages = [...t.pages.slice(0, t.cursor + 1), page].slice(-100);
      t.cursor = t.pages.length - 1;
      t.target = null;
    }
    redraw((n) => n + 1);
  }, [sourceKey, page]);

  useEffect(() => {
    let disposed = false;
    generation.current++;
    setOutline([]);
    setHits([]);
    setQuery("");
    setProgress("");
    setSearching(false);
    setScanned(0);
    if (doc)
      void (async () => {
        const rows: OutlineEntry[] = [];
        async function visit(items: any[], depth: number) {
          for (const item of items) {
            if (disposed) return;
            let target: number | null = null;
            try {
              const dest =
                typeof item.dest === "string"
                  ? await doc!.getDestination(item.dest)
                  : item.dest;
              if (Array.isArray(dest) && dest.length)
                target =
                  typeof dest[0] === "number"
                    ? dest[0]
                    : await doc!.getPageIndex(dest[0]);
            } catch {
              /* A broken destination must not prevent PDF reading. */
            }
            if (
              target !== null &&
              (!Number.isInteger(target) ||
                target < 0 ||
                target >= doc!.numPages)
            )
              target = null;
            rows.push({
              title: item.title || "未命名章节",
              page: target,
              depth,
            });
            if (item.items?.length) await visit(item.items, depth + 1);
          }
        }
        try {
          await visit((await doc.getOutline()) || [], 0);
        } catch {
          /* Outline is optional. */
        }
        if (!disposed) setOutline(rows);
      })();
    return () => {
      disposed = true;
      generation.current++;
    };
  }, [doc, sourceKey]);

  function travel(direction: number) {
    const t = trail.current,
      next = t.cursor + direction;
    if (next < 0 || next >= t.pages.length) return;
    t.cursor = next;
    t.target = t.pages[next];
    redraw((n) => n + 1);
    onNavigate(t.target);
  }

  async function search() {
    const term = query.trim().replace(/\s+/g, " ").toLocaleLowerCase();
    if (!doc || !term) return;
    const run = ++generation.current,
      result: Hit[] = [];
    let emptyPages = 0,
      unreadable = 0;
    setHits([]);
    setSearching(true);
    setScanned(0);
    for (let index = 0; index < doc.numPages; index++) {
      if (run !== generation.current) return;
      setProgress(`正在搜索第 ${index + 1} / ${doc.numPages} 页…`);
      try {
        const content = await (await doc.getPage(index + 1)).getTextContent();
        if (run !== generation.current) return;
        const text = content.items
          .map((item) => ("str" in item ? item.str : ""))
          .join(" ")
          .replace(/\s+/g, " ")
          .trim();
        if (!text) emptyPages++;
        const found = text.toLocaleLowerCase().indexOf(term);
        if (found >= 0) {
          result.push({
            page: index,
            snippet:
              (found > 60 ? "…" : "") +
              text.slice(Math.max(0, found - 60), found + term.length + 100) +
              (found + term.length + 100 < text.length ? "…" : ""),
          });
          setHits([...result]);
        }
      } catch {
        if (run !== generation.current) return;
        unreadable++;
      }
      if (run !== generation.current) return;
      setScanned(emptyPages);
      if (result.length >= 100) {
        setProgress(`显示前 100 个命中页；已搜索到第 ${index + 1} 页。`);
        setSearching(false);
        return;
      }
    }
    setProgress(
      `${result.length ? `找到 ${result.length} 个命中页` : "未找到文字匹配"} · 已搜索 ${doc.numPages} 页${unreadable ? `，${unreadable} 页未能读取` : ""}`,
    );
    setSearching(false);
  }

  const t = trail.current;
  return (
    <div className="pdf-navigation">
      <div className="pdf-navigation-actions">
        <button
          aria-label="返回上一阅读位置"
          disabled={t.cursor === 0}
          onClick={() => travel(-1)}
        >
          返回位置
        </button>
        <button
          aria-label="前进到下一阅读位置"
          disabled={t.cursor >= t.pages.length - 1}
          onClick={() => travel(1)}
        >
          前进
        </button>
        <button
          aria-expanded={open}
          aria-controls="pdf-navigation-content"
          onClick={() => setOpen(!open)}
        >
          目录与搜索
        </button>
      </div>
      {open && (
        <div id="pdf-navigation-content" className="pdf-navigation-content">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void search();
            }}
          >
            <input
              aria-label="搜索 PDF 正文"
              placeholder="在这篇论文中查找文字…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <button disabled={!doc || !query.trim() || searching}>搜索</button>
            {searching && (
              <button
                type="button"
                onClick={() => {
                  generation.current++;
                  setSearching(false);
                  setProgress("搜索已停止，保留已找到的位置。");
                }}
              >
                停止搜索
              </button>
            )}
          </form>
          {progress && <p role="status">{progress}</p>}
          {!!scanned && (
            <p className="small muted">
              {scanned} 页没有文字层；扫描图像不包含在文字搜索中。
            </p>
          )}
          {!!hits.length && (
            <ol className="pdf-search-results">
              {hits.map((hit) => (
                <li key={hit.page}>
                  <button onClick={() => onNavigate(hit.page)}>
                    <b>PDF 第 {hit.page + 1} 页</b>
                    <span>{hit.snippet}</span>
                  </button>
                </li>
              ))}
            </ol>
          )}
          <details>
            <summary>论文目录 · {outline.length} 项</summary>
            {outline.length ? (
              <ul className="pdf-outline">
                {outline.map((entry, index) => (
                  <li
                    key={index}
                    style={{ paddingLeft: Math.min(entry.depth, 8) * 12 }}
                  >
                    <button
                      disabled={entry.page === null}
                      onClick={() =>
                        entry.page !== null && onNavigate(entry.page)
                      }
                    >
                      {entry.title}
                      {entry.page !== null
                        ? ` · 第 ${entry.page + 1} 页`
                        : " · 无可用页码"}
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="small muted">
                这份 PDF 没有可用目录，可用正文搜索或页码定位。
              </p>
            )}
          </details>
        </div>
      )}
    </div>
  );
}

export type Row = { id: string; revision: number; [key: string]: any };
export const id = () => crypto.randomUUID().replaceAll("-", "");
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function api(path: string, body?: any): Promise<any> {
  const r = await fetch(
    "/api/" + path,
    body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  if (!r.ok) {
    const d = await r.json().catch(() => ({}));
    throw new ApiError(
      d.error ||
        (typeof d.detail === "string"
          ? d.detail
          : "操作未完成，请检查内容或重新打开工作台。"),
      r.status,
    );
  }
  return r.json();
}
export async function put(
  kind: string,
  data: Partial<Row>,
  operation_id = id(),
): Promise<Row> {
  return (
    await api("commit", {
      operation_id,
      mutations: [{ kind, data, expected_revision: data.revision || 0 }],
    })
  ).records[0];
}
export function anchorFor(p: Row, page: number, extra: any = {}) {
  return {
    paper_id: p.id,
    source_version: p.source_version,
    page_index: page,
    page_label: "",
    quote: "",
    rects: [],
    status: p.source_version ? "verified" : "unresolved",
    ...extra,
  };
}
export function sameAnchor(a: any, b: any): boolean {
  const normalized = (v: any) => !v ? null : {
    paper_id: v.paper_id,
    source_version: v.source_version || "",
    page_index: v.page_index ?? null,
    page_label: v.page_label || "",
    section: v.section || "",
    figure: v.figure || "",
    quote: v.quote || "",
    rects: v.rects || [],
    status: v.status || "unresolved",
    rendition: v.rendition ? {
      job_id: v.rendition.job_id, view: v.rendition.view,
      document_version: v.rendition.document_version,
      page_index: v.rendition.page_index, page_label: v.rendition.page_label || "",
      quote: v.rendition.quote || "", rects: v.rendition.rects || [],
    } : null,
  };
  return JSON.stringify(normalized(a)) === JSON.stringify(normalized(b));
}
export function location(a: any) {
  if (a?.rendition) {
    const r = a.rendition;
    return `${r.view === "dual" ? "双语" : "中文"} PDF 第 ${r.page_index + 1} 页${a.status === "stale" ? " · 旧版本，待重定位" : ""}`;
  }
  return !a
    ? "待定位"
    : `${a.page_index === null ? "待定位" : "PDF 第 " + (a.page_index + 1) + " 页"}${a.page_label ? " · 页码 " + a.page_label : ""}${a.status === "stale" ? " · 旧版本，待重定位" : a.status !== "verified" ? " · 待核实" : ""}`;
}

export const anchorQuote = (anchor: any) => anchor?.rendition?.quote || anchor?.quote || "";
/** A kept highlight or region: the words are the paper's, not a learner thought. */
export function isBareMark(note: any) {
  if (note?.author !== "user" || !note.anchor) return false;
  const quote = anchorQuote(note.anchor).trim(), content = (note.content || "").trim();
  return quote ? content === quote : content === "区域标记";
}

/** Read only geometry belonging to the displayed PDF; source and translated layouts differ. */
export function visibleAnchor(anchor: any, paper: Row, rendition?: { job_id: string; view: string; document_version: string } | null) {
  if (!anchor || anchor.paper_id !== paper.id || anchor.source_version !== paper.source_version || anchor.status === "stale") return null;
  if (!rendition) return anchor.status === "verified" ? anchor : null;
  const target = anchor.rendition;
  return target && target.job_id === rendition.job_id && target.view === rendition.view && target.document_version === rendition.document_version ? target : null;
}

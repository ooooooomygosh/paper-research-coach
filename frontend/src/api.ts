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
export function location(a: any) {
  return !a
    ? "待定位"
    : `${a.page_index === null ? "待定位" : "PDF 第 " + (a.page_index + 1) + " 页"}${a.page_label ? " · 页码 " + a.page_label : ""}${a.status === "stale" ? " · 旧版本，待重定位" : a.status !== "verified" ? " · 待核实" : ""}`;
}

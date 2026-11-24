import { workspaceApi, type RecordData } from "./workspace-api";

export function studioPaperContext(paper: RecordData | undefined, page: number, selection?: RecordData) {
  if (!paper?.source_path) return null;
  const selected = selection?.paper_id === paper.id && selection?.source_version === paper.source_version
    && selection?.status === "verified" && Number.isInteger(selection?.page_index) && selection.page_index >= 0;
  const quote = selected && typeof selection.quote === "string" ? selection.quote.trim().slice(0, 4000) : "";
  return {
    paper_id: paper.id,
    source_version: paper.source_version,
    page_index: selected ? selection.page_index : page,
    ...(quote ? { quote } : {}),
  };
}

export function createStudio(paper?: RecordData, context: RecordData = {}) {
  const title = paper && context.paper_id ? `${paper.title} · 第 ${context.page_index + 1} 页` : undefined;
  return workspaceApi("/studios", { title, context, presentation: "components" });
}

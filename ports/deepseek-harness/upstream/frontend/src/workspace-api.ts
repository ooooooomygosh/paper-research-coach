export type RecordData = Record<string, any>;

export async function workspaceApi(path = "", body?: any, method?: string) {
  const response = await fetch("/api/workspace" + path, {
    method: method || (body === undefined ? "GET" : "POST"),
    ...(body === undefined ? {} : { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(typeof error.detail === "string" ? error.detail : error.error || "操作未完成，请稍后重试。");
  }
  return response.json();
}

// fetch is prefixed by the Harness entry shim. Native frames and links need an
// explicit prefix, including when the page is hosted below /paper-research-coach/.
export const workspaceUrl = (path: string) => import.meta.env.BASE_URL + "api/workspace" + path;
export const versionQuery = (version?: string) => version ? "?version=" + encodeURIComponent(version) : "";
export const activeJob = (jobs: RecordData[], owner?: string) => jobs.find(j => j.owner === owner && ["queued", "running"].includes(j.state));
export const jobLabel: Record<string, string> = { queued: "等待中", running: "进行中", completed: "已完成", cancelled: "已停止", interrupted: "已中断", failed: "需要处理" };
export function unitProgress(progress: RecordData, unitId: string, version: string) {
  return progress[version + ":" + unitId] || (progress[unitId]?.version === version ? progress[unitId] : undefined);
}

export async function uploadMaterial(kbId: string, file: File) {
  const response = await fetch(`/api/workspace/kbs/${kbId}/materials?filename=${encodeURIComponent(file.name)}`, { method: "POST", body: file });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(typeof error.detail === "string" ? error.detail : "材料上传失败。");
  }
  return response.json();
}

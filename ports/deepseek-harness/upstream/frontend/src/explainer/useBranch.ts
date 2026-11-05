import { useCallback, useEffect, useRef, useState } from "react";
import { api, id as newId, type Row } from "../api";
import type { ExplainerRecord, ExplainerSummary } from "./types";

// One branch = one reader question plus its follow-ups. Each answer is a page.
// The hook only reads and asks; the mainline (reading route, pending question)
// lives on the server and is untouched while a branch is open.
export function useBranch(paper: Row, branchId: string, firstPageId = "") {
  const [pages, setPages] = useState<ExplainerSummary[]>([]);
  const [records, setRecords] = useState<Record<string, ExplainerRecord>>({});
  const [currentId, setCurrentId] = useState(firstPageId);
  const [busy, setBusy] = useState(false);
  const [conversationId, setConversationId] = useState("");
  const [error, setError] = useState("");
  const known = useRef<Record<string, string>>({});
  const alive = useRef(true);
  const lastSignature = useRef("");
  const wasBusy = useRef(false);

  const load = useCallback(
    async (selectNewest: boolean) => {
      try {
        const list: ExplainerSummary[] = (await api("coach/explainers/" + paper.id)).data.filter(
          (p: ExplainerSummary) => p.branch_id === branchId,
        );
        if (!alive.current) return;
        const fresh = list.filter((p) => known.current[p.id] !== p.updated_at);
        const added = list.filter((p) => !(p.id in known.current));
        setPages(list);
        const loaded = await Promise.all(
          fresh.map(async (p) => (await api("coach/explainer/" + p.id)) as ExplainerRecord),
        );
        if (!alive.current) return;
        for (const r of loaded) known.current[r.id] = r.updated_at;
        setRecords((prev) => ({ ...prev, ...Object.fromEntries(loaded.map((r) => [r.id, r])) }));
        setCurrentId((cur) =>
          selectNewest && added.length
            ? added[added.length - 1].id
            : cur && list.some((p) => p.id === cur)
              ? cur
              : list[list.length - 1]?.id || "",
        );
      } catch (e) {
        if (alive.current) setError(String(e instanceof Error ? e.message : e));
      }
    },
    [paper.id, branchId],
  );

  useEffect(() => {
    alive.current = true;
    known.current = {};
    setRecords({});
    void load(false);
    let source: EventSource | null = null;
    if (typeof EventSource !== "undefined") {
      source = new EventSource("/api/coach/events/" + paper.id);
      source.onmessage = (event) => {
        let snapshot: any;
        try {
          snapshot = JSON.parse(event.data);
        } catch {
          return;
        }
        if (!alive.current) return;
        setBusy(!!snapshot.busy);
        setConversationId(snapshot.canonical_conversation_id || snapshot.conversation_id || "");
        const signature = (snapshot.messages || [])
          .flatMap((m: any) => (m.actions || []).filter((a: any) => a.kind === "explainer" && a.branch_id === branchId))
          .map((a: any) => a.id + ":" + (a.rev || ""))
          .join(",");
        const finished = wasBusy.current && !snapshot.busy;
        wasBusy.current = !!snapshot.busy;
        if (signature !== lastSignature.current || finished) {
          lastSignature.current = signature;
          void load(true);
        }
      };
    }
    return () => {
      alive.current = false;
      source?.close();
    };
  }, [paper.id, branchId, load]);

  const ask = useCallback(
    async (text: string, page = 0) => {
      setError("");
      try {
        await api("coach/send/" + paper.id, {
          operation_id: newId(),
          conversation_id: conversationId,
          content: text,
          intent: "detour",
          help_mode: "guided",
          anchor: null,
          page_index: page,
          source_version: paper.source_version,
          model: localStorage.getItem("prc-coach-model") || "",
          effort: localStorage.getItem("prc-coach-effort") || "",
          page_image: "",
          branch_id: branchId,
        });
        setBusy(true);
        return true;
      } catch (e) {
        setError(String(e instanceof Error ? e.message : e));
        return false;
      }
    },
    [paper.id, paper.source_version, conversationId, branchId],
  );

  return { pages, record: records[currentId], currentId, setCurrentId, busy, error, ask };
}

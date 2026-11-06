// The paper's structure as the server found it (src/paper_research_coach/paper_map.py): headings with
// their pages, found automatically. It can be incomplete, so every label here is a hint about where the
// reader is, never a claim about the paper.
export type PaperMapEntry = { title: string; page_index: number; depth: number };
export type PaperMap = { outline?: PaperMapEntry[]; outline_source?: string } | null | undefined;

/** The heading that carries over from earlier pages, and the headings that start on this page. */
export function sectionsAt(map: PaperMap, pageIndex: number): { carried: string; starting: string[] } {
  let carried = "";
  const starting: string[] = [];
  for (const entry of map?.outline ?? []) {
    if (entry.page_index < pageIndex) carried = entry.title;
    else if (entry.page_index === pageIndex) starting.push(entry.title);
  }
  return { carried, starting: starting.slice(0, 3) };
}

const clip = (text: string, n = 30) => (text.length > n ? text.slice(0, n - 1) + "…" : text);

/** The chip text for the reader's page, or null when the paper's structure is unknown. */
export function sectionChip(map: PaperMap, pageIndex: number): { text: string; title: string } | null {
  const { carried, starting } = sectionsAt(map, pageIndex);
  if (!carried && !starting.length) return null;
  const parts: string[] = [];
  if (carried) parts.push(clip(carried));
  if (starting.length) parts.push((carried ? "→ " : "本页开始 ") + clip(starting[starting.length - 1]));
  const full = [carried && "承接：" + carried, starting.length && "本页开始：" + starting.join("、")].filter(Boolean).join("；");
  return { text: parts.join(" "), title: full + "（自动识别，可能不全）" };
}

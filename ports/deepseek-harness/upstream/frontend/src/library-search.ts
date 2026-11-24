import type { Row } from "./api";

export type ZoteroCollection = { key: string; name: string; parent_key: string };
export const ALL_TOPICS = "";
export const UNFILED_TOPIC = "unfiled";

export type LibraryTopics = {
  options: { key: string; label: string; count: number }[];
  members: ReadonlyMap<string, Set<string>>;
};

/** A parent collection includes its descendants. Each paper counts once per collection. */
export function indexTopics(
  papers: Row[],
  collections: ZoteroCollection[] = [],
  paperKeys: Record<string, string[]> = {},
): LibraryTopics {
  const byKey = new Map(collections.map((collection) => [collection.key, collection]));
  const paths = new Map<string, ZoteroCollection[]>();
  for (const collection of collections) {
    const seen = new Set<string>();
    const path: ZoteroCollection[] = [];
    let parent: ZoteroCollection | undefined = collection;
    while (parent && !seen.has(parent.key)) {
      seen.add(parent.key);
      path.push(parent);
      parent = byKey.get(parent.parent_key);
    }
    paths.set(collection.key, path.reverse());
  }
  const members = new Map(
    [...byKey.keys(), UNFILED_TOPIC].map((key) => [key, new Set<string>()]),
  );
  for (const paper of papers) {
    let filed = false;
    for (const key of paperKeys[paper.id] ?? []) {
      const path = paths.get(key);
      if (!path) continue;
      filed = true;
      for (const entry of path) members.get(entry.key)?.add(paper.id);
    }
    if (!filed) members.get(UNFILED_TOPIC)?.add(paper.id);
  }
  const topics = collections
    .map(({ key, name }) => ({
      key,
      label: paths.get(key)?.map((entry) => entry.name).join(" / ") || name,
      count: members.get(key)?.size ?? 0,
    }))
    .sort((a, b) => a.label.localeCompare(b.label, "zh-Hans"));
  return {
    options: [
      { key: ALL_TOPICS, label: "全部论文", count: papers.length },
      ...topics,
      ...(topics.length
        ? [{ key: UNFILED_TOPIC, label: "未分类", count: members.get(UNFILED_TOPIC)!.size }]
        : []),
    ],
    members,
  };
}

export function papersInTopic(papers: Row[], topics: LibraryTopics | undefined, topic: string) {
  const members = topics?.members.get(topic);
  return members ? papers.filter((paper) => members.has(paper.id)) : papers;
}

function normalize(value: unknown) {
  return String(value ?? "").normalize("NFKC").toLocaleLowerCase().trim();
}

/** AND matching across bibliographic fields; no fuzzy inference about the paper. */
export function filterPapers(papers: Row[], query: string): Row[] {
  const terms = normalize(query).split(/\s+/u).filter(Boolean);
  if (!terms.length) return papers;
  return papers.filter((paper) => {
    const text = [paper.title, paper.authors, paper.year, paper.doi, paper.publication]
      .map(normalize).join(" ");
    return terms.every((term) => text.includes(term));
  });
}

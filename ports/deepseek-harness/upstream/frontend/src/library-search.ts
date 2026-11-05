import type { Row } from "./api";

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

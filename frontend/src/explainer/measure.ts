// Text size without a canvas: CJK characters are one em wide, Latin about 0.56 em.
const CJK = /[⺀-鿿＀-￯]/;

export function textWidth(text: string, fontSize: number): number {
  let width = 0;
  for (const ch of text) {
    width += CJK.test(ch) ? fontSize : /[A-Z0-9MW@%]/.test(ch) ? fontSize * 0.66 : fontSize * 0.56;
  }
  return width;
}

// Greedy wrap: Latin text breaks at spaces, CJK text between any two characters.
export function wrapText(text: string, fontSize: number, maxWidth: number): string[] {
  const lines: string[] = [];
  let line = "";
  const tokens = text.match(/[⺀-鿿＀-￯]|[^\s⺀-鿿＀-￯]+|\s+/g) ?? [];
  for (const token of tokens) {
    const next = line + token;
    if (line && textWidth(next.trimEnd(), fontSize) > maxWidth) {
      lines.push(line.trimEnd());
      line = token.trimStart();
    } else {
      line = next;
    }
  }
  if (line.trim()) lines.push(line.trimEnd());
  return lines.length ? lines : [""];
}

export function plain(markdown: string): string {
  return markdown
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/`([^`]*)`/g, "$1")
    .replace(/\$([^$]+)\$/g, "$1")
    .replace(/[*_]{1,3}/g, "");
}

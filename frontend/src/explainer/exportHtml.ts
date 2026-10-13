import sheetCss from "./explainer.css?raw";
import katexCss from "katex/dist/katex.min.css?raw";

const escapeHtml = (s: string) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);

/** The current values of the colour tokens the styles use, so the file looks the same offline. */
function tokens(css: string) {
  const names = new Set(Array.from(css.matchAll(/var\((--[\w-]+)/g), (m) => m[1]));
  const style = getComputedStyle(document.documentElement);
  return Array.from(names)
    .map((name) => [name, style.getPropertyValue(name).trim()])
    .filter(([, value]) => value)
    .map(([name, value]) => `${name}: ${value};`)
    .join(" ");
}

/**
 * A single, offline HTML file of an explainer page as it is drawn now: the rendered DOM (diagrams
 * are already inline SVG) plus the sheet's styles. No script is copied, and buttons and inputs
 * are removed, so the file is a static page.
 */
export function explainerHtml(root: HTMLElement, meta: { title: string; source?: string; css?: string }) {
  const css = sheetCss + "\n" + (meta.css || "");
  const page = root.cloneNode(true) as HTMLElement;
  // Links into the workbench (data-export="text") keep their words as plain text; folded parts open.
  page.querySelectorAll<HTMLElement>("button[data-export='text']").forEach((b) => {
    const span = document.createElement("span");
    span.className = b.className;
    span.append(...Array.from(b.childNodes));
    b.replaceWith(span);
  });
  page.querySelectorAll("details").forEach((d) => d.setAttribute("open", ""));
  page.querySelectorAll("script, [data-export='skip'], button, textarea, input[type='text']").forEach((e) => e.remove());
  page.querySelectorAll("input").forEach((e) => e.setAttribute("disabled", ""));
  const made = new Date().toLocaleString();
  return `<!doctype html>
<html lang="${escapeHtml(page.getAttribute("lang") || "zh-CN")}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(meta.title)}</title>
<style>
:root { ${tokens(css)} }
body { margin: 0; background: var(--bg, #f4f6f2); color: var(--text, #203229); font: 15px/1.7 -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif; }
main.xp-export { max-width: 1040px; margin: 0 auto; padding: 28px 20px 40px; }
main.xp-export > h1 { margin: 0 0 12px; font-size: 24px; line-height: 1.3; }
main.xp-export > footer { margin-top: 24px; font-size: 12px; color: var(--muted, #6b7a70); }
${css}
${katexCss}
</style>
</head>
<body>
<main class="xp-export">
<h1>${escapeHtml(meta.title)}</h1>
${page.outerHTML}
<footer>${escapeHtml(meta.source ? meta.source + " · " : "")}Paper Research Coach · ${escapeHtml(made)}</footer>
</main>
</body>
</html>
`;
}

export function downloadHtml(html: string, name: string) {
  const url = URL.createObjectURL(new Blob([html], { type: "text/html;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = (name.replace(/[\\/:*?"<>|]+/g, " ").trim() || "explainer").slice(0, 80) + ".html";
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkCjkFriendly from "remark-cjk-friendly";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

// Draft text is data. react-markdown never renders raw HTML, images are dropped,
// and links open in a new tab without a referrer.
const plugins = { remark: [remarkGfm, remarkCjkFriendly, remarkMath] as any[], rehype: [rehypeKatex] as any[] };
const base = {
  remarkPlugins: plugins.remark,
  rehypePlugins: plugins.rehype,
  disallowedElements: ["img", "script", "iframe"],
  unwrapDisallowed: true,
};
// react-markdown also passes the syntax-tree `node`; spread onto <a> it would become node="[object Object]".
const link = ({ node: _node, ...props }: any) => <a {...props} target="_blank" rel="noopener noreferrer" />;

// Quotes and list markers nest as deep as the text says: "- - - - … x" is 2 bytes a level, and a few
// thousand levels overflow the stack inside Markdown. Real explanations nest 3 or 4 deep.
const MAX_NESTING = 20;
export function nestingDepth(text: string): number {
  let deepest = 0;
  for (const raw of text.split("\n")) {
    let rest = raw.slice(0, 4000).trimStart();
    let depth = 0;
    for (;;) {
      const m = rest.match(/^(?:>\s?|[-*+]\s+|\d{1,9}[.)]\s+)/);
      if (!m) break;
      depth += 1;
      rest = rest.slice(m[0].length).trimStart();
    }
    deepest = Math.max(deepest, depth);
  }
  return deepest;
}
const guard = (text: string) => {
  if (nestingDepth(text) > MAX_NESTING) throw new Error("explainer text nests too deeply to draw");
  return text;
};

export function Inline({ text }: { text: string }) {
  return (
    <Markdown {...base} components={{ p: ({ children }) => <>{children}</>, a: link }}>
      {guard(text)}
    </Markdown>
  );
}

// A table cell that starts with ok / no / warn becomes a badge.
function Cell({ children, header }: { children?: any; header?: boolean }) {
  const parts = Array.isArray(children) ? children : [children];
  const first = typeof parts[0] === "string" ? (parts[0] as string) : "";
  const m = !header && parts.length === 1 ? first.match(/^(ok|no|warn)(?:\s+([\s\S]*))?$/) : null;
  if (!m) return header ? <th>{children}</th> : <td>{children}</td>;
  const mark = { ok: "✓", no: "✗", warn: "!" }[m[1] as "ok" | "no" | "warn"];
  const label = { ok: "是", no: "否", warn: "注意" }[m[1] as "ok" | "no" | "warn"];
  return (
    <td>
      <span className={"xp-badge " + m[1]} role="img" aria-label={label}>
        {mark}
      </span>
      {m[2] ? " " + m[2] : ""}
    </td>
  );
}

export function Prose({ text }: { text: string }) {
  return (
    <div className="xp-prose">
      <Markdown
        {...base}
        components={{
          a: link,
          td: (p) => <Cell>{p.children}</Cell>,
          th: (p) => <Cell header>{p.children}</Cell>,
          table: (p) => (
            <div className="xp-table-wrap">
              <table>{p.children}</table>
            </div>
          ),
        }}
      >
        {guard(text)}
      </Markdown>
    </div>
  );
}

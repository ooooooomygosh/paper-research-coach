// The server parses a model's Markdown draft into this typed JSON (src/paper_research_coach/explainer.py).
// The browser only draws it: no draft text is ever injected as HTML or run as code.
export type MdBlock = { type: "md"; text: string; line: number };
export type FlowNode = {
  id: string;
  label: string;
  shape: "rect" | "round" | "diamond" | "db";
  hi: boolean;
};
export type FlowEdge = { from: string; to: string; dashed: boolean; label: string };
export type FlowBlock = {
  type: "flow";
  dir: "TB" | "LR" | "BT" | "RL";
  nodes: FlowNode[];
  edges: FlowEdge[];
  groups: { name: string; members: string[] }[];
};
export type SeqStep =
  | { kind: "msg"; from: string; to: string; dashed: boolean; label: string }
  | { kind: "note"; over: string[]; text: string }
  | { kind: "divider"; text: string };
export type SequenceBlock = {
  type: "sequence";
  participants: string[];
  steps: SeqStep[];
  numbered: boolean;
};
export type TreeNode = { label: string; note: string; hi: boolean; children: TreeNode[] };
export type TreeBlock = { type: "tree"; roots: TreeNode[]; list: boolean };
export type TimelineBlock = {
  type: "timeline";
  items: { when: string; title: string; detail: string; hi: boolean }[];
  vertical: boolean;
};
export type CalloutBlock = {
  type: "callout";
  kind: "info" | "ok" | "warn" | "err";
  title: string;
  text: string;
};
export type AskBlock = {
  type: "ask";
  question: string;
  options: { label: string; note: string; suggested: boolean }[];
  multi: boolean;
};
export type KvBlock = {
  type: "kv";
  cols: number;
  cells: { key: string; value: string; wide: boolean }[];
};
export type Block =
  | MdBlock
  | FlowBlock
  | SequenceBlock
  | TreeBlock
  | TimelineBlock
  | CalloutBlock
  | AskBlock
  | KvBlock;
export type ExplainerDoc = {
  title: string;
  subtitle: string;
  lang: string;
  lead: Block[];
  panels: { title: string; blocks: Block[] }[];
};
export type ReturnPoint = {
  status: string;
  step: string;
  label: string;
  pending_question: string;
  next_action: string;
};
export type ExplainerRecord = {
  id: string;
  paper_id: string;
  branch_id: string;
  seq: number;
  title: string;
  question: string;
  doc: ExplainerDoc;
  warnings: string[];
  anchor: any;
  return_point: ReturnPoint;
  created_at: string;
  updated_at: string;
};
export type ExplainerSummary = Pick<
  ExplainerRecord,
  "id" | "branch_id" | "seq" | "title" | "question" | "created_at" | "updated_at" | "return_point"
>;

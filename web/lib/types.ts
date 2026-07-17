export type NodeType = "input" | "retrieve" | "llm" | "tool" | "output";

export interface FlowNode {
  id: string;
  type: NodeType;
  x: number;
  y: number;
  config?: Record<string, unknown>;
}

export interface FlowEdge {
  from: string;
  to: string;
}

export interface RunEvent {
  runId: string;
  node: string;
  phase: string; // start | token | tool_call | tool_result | node_done | done | error
  text?: string;
  data?: Record<string, unknown>;
  ts: number;
}

export const NODE_META: Record<NodeType, { label: string; color: string; lang: string }> = {
  input: { label: "Input", color: "#6b7a99", lang: "—" },
  retrieve: { label: "Retrieve (RAG)", color: "var(--python)", lang: "Python" },
  llm: { label: "LLM", color: "var(--python)", lang: "Python" },
  tool: { label: "Tool (Rust)", color: "var(--rust)", lang: "Rust" },
  output: { label: "Output", color: "var(--ts)", lang: "TypeScript" },
};

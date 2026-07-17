"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { FlowEdge, FlowNode, NODE_META, NodeType, RunEvent } from "@/lib/types";

const GATEWAY_WS =
  process.env.NEXT_PUBLIC_GATEWAY_WS || "ws://localhost:8080/ws";
const TOKEN = process.env.NEXT_PUBLIC_TOKEN || "dev-token";

const NODE_W = 168;
const NODE_H = 56;

const INITIAL_NODES: FlowNode[] = [
  { id: "in", type: "input", x: 60, y: 60 },
  { id: "rag", type: "retrieve", x: 300, y: 60, config: { k: 3 } },
  { id: "brain", type: "llm", x: 540, y: 60, config: { system: "You are an agent in the mesh." } },
  { id: "cost", type: "tool", x: 300, y: 200, config: { tool: "eval", expr: "tokens * 0.000002" } },
  { id: "out", type: "output", x: 540, y: 200 },
];
const INITIAL_EDGES: FlowEdge[] = [
  { from: "in", to: "rag" },
  { from: "rag", to: "brain" },
  { from: "brain", to: "cost" },
  { from: "cost", to: "out" },
];

type Status = "idle" | "running" | "done" | "error";

export default function Page() {
  const [nodes, setNodes] = useState<FlowNode[]>(INITIAL_NODES);
  const [edges, setEdges] = useState<FlowEdge[]>(INITIAL_EDGES);
  const [connectFrom, setConnectFrom] = useState<string | null>(null);
  const [status, setStatus] = useState<Record<string, Status>>({});
  const [input, setInput] = useState("How does the Go gateway scale?");
  const [log, setLog] = useState<string[]>([]);
  const [reply, setReply] = useState("");
  const [finalText, setFinalText] = useState("");
  const [connected, setConnected] = useState(false);
  const [running, setRunning] = useState(false);

  const svgRef = useRef<SVGSVGElement | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const drag = useRef<{ id: string; dx: number; dy: number } | null>(null);

  const addLog = useCallback((line: string) => {
    setLog((l) => [...l.slice(-200), line]);
  }, []);

  const handleEvent = useCallback((ev: RunEvent) => {
    switch (ev.phase) {
      case "start":
        setStatus((s) => ({ ...s, [ev.node]: "running" }));
        break;
      case "token":
        setReply((r) => r + (ev.text || ""));
        break;
      case "tool_call":
        addLog(`⚙ ${ev.node} tool_call ${JSON.stringify(ev.data)}`);
        break;
      case "tool_result":
        addLog(`↳ ${ev.node} result ${JSON.stringify(ev.data)}`);
        break;
      case "node_done":
        setStatus((s) => ({ ...s, [ev.node]: "done" }));
        break;
      case "done":
        setFinalText(ev.text || "");
        setRunning(false);
        addLog("● run complete");
        break;
      case "error":
        setStatus((s) => ({ ...s, [ev.node]: "error" }));
        setRunning(false);
        break;
    }
  }, [addLog]);

  // ---- WebSocket to the Go gateway ----
  useEffect(() => {
    const ws = new WebSocket(GATEWAY_WS);
    wsRef.current = ws;
    ws.onopen = () => {
      setConnected(true);
      ws.send(JSON.stringify({ type: "auth", token: TOKEN }));
      addLog("→ connected to gateway, authenticating");
    };
    ws.onclose = () => setConnected(false);
    ws.onerror = () => addLog("⚠ gateway connection error (is the Go gateway running?)");
    ws.onmessage = (e) => {
      let msg: { type: string; ok?: boolean; event?: RunEvent; message?: string };
      try {
        msg = JSON.parse(e.data);
      } catch {
        return;
      }
      if (msg.type === "authed") addLog(msg.ok ? "✓ authenticated" : "✗ auth rejected");
      else if (msg.type === "error") addLog(`⚠ ${msg.message}`);
      else if (msg.type === "event" && msg.event) handleEvent(msg.event);
    };
    return () => ws.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---- run ----
  const run = () => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      addLog("⚠ not connected");
      return;
    }
    setReply("");
    setFinalText("");
    setStatus({});
    setRunning(true);
    const workflow = {
      nodes: nodes.map((n) => ({ id: n.id, type: n.type, config: n.config || {} })),
      edges: edges.map((e) => ({ from: e.from, to: e.to })),
    };
    ws.send(JSON.stringify({ type: "run", runId: `r-${Date.now()}`, workflow, input }));
    addLog(`▶ run dispatched (${nodes.length} nodes)`);
  };

  // ---- canvas interaction ----
  const toSvg = (clientX: number, clientY: number) => {
    const rect = svgRef.current?.getBoundingClientRect();
    return { x: clientX - (rect?.left || 0), y: clientY - (rect?.top || 0) };
  };

  const onNodePointerDown = (e: React.PointerEvent, n: FlowNode) => {
    e.stopPropagation();
    (e.target as Element).setPointerCapture?.(e.pointerId);
    const p = toSvg(e.clientX, e.clientY);
    drag.current = { id: n.id, dx: p.x - n.x, dy: p.y - n.y };
  };
  const onPointerMove = (e: React.PointerEvent) => {
    if (!drag.current) return;
    const p = toSvg(e.clientX, e.clientY);
    const d = drag.current;
    setNodes((ns) => ns.map((n) => (n.id === d.id ? { ...n, x: p.x - d.dx, y: p.y - d.dy } : n)));
  };
  const onPointerUp = () => {
    drag.current = null;
  };

  const onNodeClick = (n: FlowNode) => {
    if (drag.current) return;
    if (!connectFrom) {
      setConnectFrom(n.id);
    } else if (connectFrom !== n.id) {
      setEdges((es) =>
        es.some((e) => e.from === connectFrom && e.to === n.id)
          ? es
          : [...es, { from: connectFrom, to: n.id }]
      );
      setConnectFrom(null);
    } else {
      setConnectFrom(null);
    }
  };

  const addNode = (type: NodeType) => {
    const id = `${type}-${Math.random().toString(36).slice(2, 6)}`;
    setNodes((ns) => [...ns, { id, type, x: 80 + Math.random() * 120, y: 320 }]);
  };

  const center = (n: FlowNode) => ({ x: n.x + NODE_W / 2, y: n.y + NODE_H / 2 });
  const byId = (id: string) => nodes.find((n) => n.id === id);

  return (
    <main style={{ display: "grid", gridTemplateColumns: "1fr 360px", height: "100vh" }}>
      {/* ---- canvas ---- */}
      <section style={{ position: "relative", overflow: "hidden" }}>
        <header style={{ padding: "14px 18px", display: "flex", gap: 12, alignItems: "center" }}>
          <strong style={{ fontSize: 18 }}>agentmesh</strong>
          <span style={{ color: "var(--muted)" }}>
            polyglot agent mesh · TypeScript · Go · Python · Rust
          </span>
          <span style={{ marginLeft: "auto", color: connected ? "var(--go)" : "var(--muted)" }}>
            {connected ? "● gateway online" : "○ offline"}
          </span>
        </header>

        <div style={{ padding: "0 18px 10px", display: "flex", gap: 8, flexWrap: "wrap" }}>
          {(Object.keys(NODE_META) as NodeType[]).map((t) => (
            <button key={t} className="ghost" onClick={() => addNode(t)}>
              + {NODE_META[t].label}
            </button>
          ))}
          <span style={{ color: "var(--muted)", alignSelf: "center", marginLeft: 8 }}>
            {connectFrom
              ? `connecting from ${connectFrom}… click a target node`
              : "click a node then another to connect · drag to move"}
          </span>
        </div>

        <svg
          ref={svgRef}
          style={{ width: "100%", height: "calc(100vh - 96px)" }}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
        >
          <defs>
            <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto">
              <path d="M0,0 L8,3 L0,6 Z" fill="var(--border)" />
            </marker>
          </defs>
          {edges.map((e, i) => {
            const a = byId(e.from);
            const b = byId(e.to);
            if (!a || !b) return null;
            const ca = center(a);
            const cb = center(b);
            return (
              <line
                key={i}
                x1={ca.x}
                y1={ca.y}
                x2={cb.x}
                y2={cb.y}
                stroke="var(--border)"
                strokeWidth={2}
                markerEnd="url(#arrow)"
              />
            );
          })}
          {nodes.map((n) => {
            const meta = NODE_META[n.type];
            const st = status[n.id] || "idle";
            const stroke =
              st === "running" ? "var(--accent)" : st === "done" ? "var(--go)" : st === "error" ? "#e2703a" : "var(--border)";
            return (
              <g
                key={n.id}
                className="node"
                transform={`translate(${n.x},${n.y})`}
                style={{ cursor: "grab" }}
                onPointerDown={(e) => onNodePointerDown(e, n)}
                onClick={() => onNodeClick(n)}
              >
                <rect
                  width={NODE_W}
                  height={NODE_H}
                  rx={10}
                  fill="var(--panel)"
                  stroke={connectFrom === n.id ? "var(--python)" : stroke}
                  strokeWidth={2}
                />
                <rect width={6} height={NODE_H} rx={3} fill={meta.color} />
                <text x={16} y={24} fill="var(--text)" fontWeight={600} fontSize={13}>
                  {meta.label}
                </text>
                <text x={16} y={42} fill="var(--muted)" fontSize={11}>
                  {n.id} · {meta.lang}
                </text>
              </g>
            );
          })}
        </svg>
      </section>

      {/* ---- run panel ---- */}
      <aside
        style={{
          borderLeft: "1px solid var(--border)",
          background: "var(--panel)",
          padding: 16,
          display: "flex",
          flexDirection: "column",
          gap: 12,
          overflow: "hidden",
        }}
      >
        <label style={{ color: "var(--muted)" }}>Input</label>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          rows={3}
          style={{
            background: "var(--bg)",
            color: "var(--text)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            padding: 10,
            resize: "vertical",
          }}
        />
        <button onClick={run} disabled={!connected || running}>
          {running ? "Running…" : "▶ Run workflow"}
        </button>

        <div>
          <div style={{ color: "var(--muted)", marginBottom: 4 }}>Streamed answer</div>
          <div
            style={{
              minHeight: 60,
              background: "var(--bg)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              padding: 10,
              whiteSpace: "pre-wrap",
            }}
          >
            {reply || <span style={{ color: "var(--muted)" }}>—</span>}
          </div>
        </div>

        {finalText && (
          <div>
            <div style={{ color: "var(--muted)", marginBottom: 4 }}>Final output</div>
            <div
              style={{
                background: "#14233b",
                border: "1px solid var(--border)",
                borderRadius: 8,
                padding: 10,
                fontFamily: "monospace",
              }}
            >
              {finalText}
            </div>
          </div>
        )}

        <div style={{ color: "var(--muted)" }}>Event log</div>
        <div
          style={{
            flex: 1,
            minHeight: 0,
            overflowY: "auto",
            background: "var(--bg)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            padding: 10,
            fontFamily: "monospace",
            fontSize: 12,
          }}
        >
          {log.map((l, i) => (
            <div key={i} style={{ color: "var(--muted)" }}>
              {l}
            </div>
          ))}
        </div>
      </aside>
    </main>
  );
}

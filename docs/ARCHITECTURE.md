# agentmesh architecture

Each language owns the layer it is structurally best at, and the layers talk over
a single JSON contract (`proto/protocol.md`) so any one can be swapped without
touching its neighbours.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Browser · Next.js + TypeScript                                           │
│  drag-and-drop node canvas · live event stream · barge-free WebSocket     │
└───────────────┬───────────────────────────────────────────────────────────┘
                │  WebSocket  (auth, run, cancel  ⇄  streamed events)
┌───────────────▼───────────────────────────────────────────────────────────┐
│  Gateway · Go                                                             │
│  one goroutine per connection · token auth · round-robin load-balancer     │
│  relays SSE from workers back over each client's single writer goroutine   │
└───────────────┬───────────────────────────────────────────────────────────┘
                │  HTTP  POST /v1/run  →  text/event-stream
┌───────────────▼───────────────────────────────────────────────────────────┐
│  Intelligence · Python                                                    │
│  LangGraph-style DAG engine · RAG retrieval · streaming LLM (mock/real)    │
│  hands heavy compute down to Rust                                          │
└───────────────┬───────────────────────────────────────────────────────────┘
                │  HTTP  /v1/tokenize · /v1/eval · /v1/csv
┌───────────────▼───────────────────────────────────────────────────────────┐
│  Executor · Rust (axum)                                                   │
│  sandboxed DSL eval · fast tokenization · CSV aggregation · resource-bound │
└───────────────────────────────────────────────────────────────────────────┘
```

## Why each language

| Layer | Language | Reason |
| --- | --- | --- |
| Interface | **TypeScript / Next.js** | React + SVG canvas is the strongest way to build stateful, real-time UIs. |
| Gateway | **Go** | Goroutines make tens of thousands of concurrent WebSocket streams cheap; low, predictable memory. |
| Intelligence | **Python** | The AI ecosystem (LangChain-style graphs, LLM SDKs, vector search) lives here. |
| Execution | **Rust** | C-level speed with memory safety and no GC pauses for sandboxed compute at the edge. |

## Request lifecycle

1. The browser builds a workflow (nodes + edges) on the canvas and sends
   `{type:"run", workflow, input}` over the WebSocket.
2. The Go gateway authenticates the socket, picks an intelligence worker
   round-robin, and `POST`s the run. It relays the worker's SSE events straight
   back to that client's writer goroutine.
3. The Python engine executes the DAG in topological order. `retrieve` nodes hit
   the vector store; `llm` nodes stream tokens; `tool` nodes call Rust.
4. The Rust executor evaluates the sandboxed expression / tokenizes / aggregates
   the CSV and returns a result, which the engine threads to downstream nodes.
5. Every step is emitted as a `RunEvent`, so the UI shows nodes lighting up, live
   tokens, and tool results as they happen.

## Offline-first

The whole mesh runs with **no API keys**:

* the LLM defaults to a deterministic mock;
* the Python layer ships a pure-Python mirror of the Rust ops, so the
  intelligence service (and its tests) run even when the Rust binary isn't up —
  set `AGENTMESH_EXECUTOR_URL` to route heavy compute to the real Rust service.

This means `docker compose up` gives you a working, clickable mesh immediately,
and each service is independently testable.

## Scaling notes

* **Gateway**: stateless; run N replicas behind an L4 load balancer. The client
  writer-goroutine + bounded send channel drop slow-consumer frames rather than
  stalling the hub.
* **Intelligence**: horizontally scalable workers; the gateway's round-robin
  balancer (`AGENTMESH_INTEL_URLS`) spreads runs across them.
* **Executor**: CPU-bound and stateless — scale to cores; safe to run many
  replicas or compile to WebAssembly for edge deployment.

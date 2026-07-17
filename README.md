# agentmesh 🕸️

**A distributed, polyglot AI agent mesh** where each language owns exactly the
layer it's built for — and they all speak one JSON contract, so any layer can be
swapped without touching its neighbours.

```
Browser ──WebSocket──▶ Go gateway ──HTTP/SSE──▶ Python intelligence ──HTTP──▶ Rust executor
(Next.js UI)          (auth + fan-out)         (agent graph + RAG + LLM)     (sandbox + tokenize + CSV)
```

| Layer | Language | Owns |
| --- | --- | --- |
| **Interface** | TypeScript / Next.js | Drag-and-drop workflow canvas, live event streaming |
| **Gateway** | Go | Auth, tens-of-thousands of WebSockets, load-balancing |
| **Intelligence** | Python | LangGraph-style agent DAG, RAG, streaming LLM |
| **Execution** | Rust (axum) | Sandboxed eval, fast tokenization, CSV aggregation |

The whole mesh runs **offline with zero API keys** — the LLM defaults to a
deterministic mock, and the Python layer carries a pure-Python mirror of the Rust
ops so every service is independently runnable and testable.

## Quickstart — the whole mesh

```bash
docker compose up --build
# UI:        http://localhost:3000   (drag nodes, hit Run, watch them light up)
# Gateway:   http://localhost:8080/health
# Intel:     http://localhost:8081/health
# Executor:  http://localhost:8082/health
```

## Quickstart — no Docker

Each layer stands alone.

```bash
# Rust executor
cd executor && cargo run                       # :8082

# Python intelligence (points at the Rust executor if it's up, else runs the mirror)
cd intelligence && pip install -e ".[server,http]"
AGENTMESH_EXECUTOR_URL=http://localhost:8082 agentmesh-intel serve   # :8081

# Go gateway
cd gateway && AGENTMESH_INTEL_URLS=http://localhost:8081 go run .     # :8080

# Next.js UI
cd web && npm install && npm run dev            # :3000
```

Or run the agent brain entirely offline, no services at all:

```bash
cd intelligence && python -m agentmesh_intelligence.cli run \
  --input "How does the Go gateway scale?"
python scripts/verify.py   # offline end-to-end check
```

## What a run looks like

The demo workflow is `input → retrieve (RAG) → llm → tool:eval (cost estimate) → output`:

```
▶ in (input)
▶ rag (retrieve)      ↳ result {"retrieved": ["arch-go", ...]}
▶ brain (llm)         ⚙ tool_call {"tool":"tokenize","engine":"rust"}   ← Rust counts tokens
   Based on the retrieved context, here is what I found ...              ← streamed
▶ cost (tool)         ⚙ tool_call {"tool":"eval"}                        ← Rust sandbox
                      ↳ result {"ok": true, "value": 0.00042}
▶ out (output)
FINAL: 0.00042
```

## The interesting engineering

- **Go gateway** — one goroutine per socket, a bounded per-client send channel and
  a single writer goroutine (so concurrent run streams can't corrupt frames), and
  a round-robin balancer across intelligence workers. `gateway/`
- **Python engine** — a real DAG executor: topological order with cycle detection,
  streaming events, and function-calling that delegates heavy compute downward.
  `intelligence/agentmesh_intelligence/engine.py`
- **Rust executor** — a genuinely *safe* "run some code" tool: a bounded
  arithmetic/logic DSL (no I/O, no loops, no calls), plus tokenization and CSV
  aggregation with no external crates beyond axum/serde. `executor/src/`
- **Next.js canvas** — hand-rolled SVG node editor (drag, connect) with a live
  WebSocket feed lighting up nodes as the run progresses. `web/app/page.tsx`
- **One protocol** — `proto/protocol.md` is the only coupling between layers.

## Testing

```bash
make test          # rust + python + go suites
cd executor     && cargo test
cd intelligence && pytest -q
cd gateway      && go test ./...
cd web          && npm run build
```

## Layout

```
proto/           shared JSON wire protocol (the only cross-layer coupling)
web/             Next.js + TypeScript dashboard (drag-and-drop canvas)
gateway/         Go WebSocket gateway (auth, hub, round-robin, SSE relay)
intelligence/    Python agent engine (DAG, RAG, LLM) + FastAPI + offline mirror
executor/        Rust axum service (sandbox eval, tokenizer, CSV)
scripts/         offline verifier
docs/            ARCHITECTURE.md
```

## License

MIT © 2026 Akhil Vase

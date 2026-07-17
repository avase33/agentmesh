# agentmesh wire protocol

Every layer speaks JSON over HTTP or WebSocket, so any service can be rewritten in
any language without touching its neighbours. This file is the single source of
truth for the messages exchanged between the four layers.

```
Browser ──WebSocket──▶ Go gateway ──HTTP/SSE──▶ Python intelligence ──HTTP──▶ Rust executor
        ◀──events────           ◀──events────                      ◀──result──
```

## 1. Browser ⇄ Gateway  (WebSocket, `/ws`)

Client → gateway:

```jsonc
{ "type": "auth", "token": "dev-token" }
{ "type": "run", "runId": "r-1", "workflow": { /* Workflow */ }, "input": "hello" }
{ "type": "cancel", "runId": "r-1" }
{ "type": "ping" }
```

Gateway → client:

```jsonc
{ "type": "authed", "ok": true }
{ "type": "event", "runId": "r-1", "event": { /* RunEvent */ } }
{ "type": "pong" }
{ "type": "error", "message": "..." }
```

## 2. Gateway ⇄ Intelligence  (HTTP, `POST /v1/run`, streamed as SSE)

Request body:

```jsonc
{ "runId": "r-1", "workflow": { /* Workflow */ }, "input": "hello", "context": {} }
```

Response: `text/event-stream`, one `data:` line per `RunEvent` (see below), ending
with an event whose `phase` is `"done"`.

## 3. Intelligence ⇄ Executor  (HTTP, Rust)

```jsonc
POST /v1/tokenize  { "text": "..." }              -> { "tokens": [..], "count": 12 }
POST /v1/eval      { "expr": "a * 2 + 1", "vars": { "a": 20 } } -> { "ok": true, "value": 41 }
POST /v1/csv       { "csv": "...", "op": "sum", "column": "amount" } -> { "rows": 100, "result": 42.0 }
GET  /health       -> { "status": "ok" }
```

The executor is **sandboxed**: `eval` runs a small arithmetic/logic DSL — never
arbitrary code — and every request is bounded by size and time limits.

## Shared types

### Workflow

```jsonc
{
  "nodes": [
    { "id": "in",   "type": "input" },
    { "id": "rag",  "type": "retrieve", "config": { "k": 3 } },
    { "id": "brain","type": "llm",      "config": { "system": "You are helpful." } },
    { "id": "calc", "type": "tool",     "config": { "tool": "eval", "expr": "tokens * 0.000002" } },
    { "id": "out",  "type": "output" }
  ],
  "edges": [
    { "from": "in", "to": "rag" },
    { "from": "rag", "to": "brain" },
    { "from": "brain", "to": "calc" },
    { "from": "calc", "to": "out" }
  ]
}
```

Node `type` values: `input`, `retrieve`, `llm`, `tool`, `output`.
Tool `tool` values: `tokenize`, `eval`, `csv` (all executed by Rust).

### RunEvent

```jsonc
{
  "runId": "r-1",
  "node": "brain",
  "phase": "start | token | tool_call | tool_result | node_done | done | error",
  "text": "partial token text",   // for phase=token
  "data": { },                     // structured payload for tool_call/tool_result
  "ts": 1730000000.0
}
```

"""FastAPI service for the intelligence layer.

Exposes ``POST /v1/run`` which the Go gateway calls; the agent run is streamed
back as Server-Sent Events (one ``data:`` line per RunEvent). Requires the
``server`` extra: ``pip install 'agentmesh-intelligence[server]'``.
"""

from __future__ import annotations

import json
from typing import Any

from .engine import AgentEngine
from .models import Workflow

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse, StreamingResponse
except ImportError as e:  # pragma: no cover
    raise RuntimeError("Install server extras: pip install 'agentmesh-intelligence[server]'") from e

app = FastAPI(title="agentmesh-intelligence", version="0.1.0")
_engine = AgentEngine()


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse(
        {
            "status": "ok",
            "service": "intelligence",
            "llm": _engine.llm.name,
            "executor": "rust" if _engine.executor.remote else "local",
            "kb_docs": len(_engine.store),
        }
    )


@app.post("/v1/run")
async def run(req: Request) -> StreamingResponse:
    body: dict[str, Any] = await req.json()
    run_id = body.get("runId", "run")
    workflow = Workflow.from_dict(body.get("workflow", {}))
    input_text = body.get("input", "")

    async def sse():
        async for ev in _engine.run(run_id, workflow, input_text):
            yield f"data: {json.dumps(ev.to_dict())}\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream")

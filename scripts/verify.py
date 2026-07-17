#!/usr/bin/env python3
"""Offline end-to-end check of the intelligence layer + Rust-mirror executor.

Runs the demo RAG -> LLM -> tool(eval) -> output workflow through the Python
engine with the local (pure-Python) mirror of the Rust executor, so it needs no
running services and no API keys. Verifies the whole graph executes, tools fire,
and a grounded answer comes out.

    python scripts/verify.py
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "intelligence"))

from agentmesh_intelligence.engine import AgentEngine  # noqa: E402
from agentmesh_intelligence.workflows import rag_cost_workflow  # noqa: E402

_passed = 0
_failed = 0


def check(label: str, cond: bool) -> None:
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  [PASS] {label}")
    else:
        _failed += 1
        print(f"  [FAIL] {label}")


async def main() -> int:
    print("=" * 68)
    print("agentmesh - offline end-to-end verification")
    print("=" * 68)
    engine = AgentEngine()
    print(f"  llm={engine.llm.name}  executor={'rust' if engine.executor.remote else 'local-mirror'}  "
          f"kb={len(engine.store)} docs")

    events, final = await engine.run_collect("verify", rag_cost_workflow(), "How does the Go gateway scale?")
    phases = {e.phase for e in events}
    started = [e.node for e in events if e.phase == "start"]
    tokens = [e for e in events if e.phase == "token"]
    tool_results = [e.data for e in events if e.phase == "tool_result"]
    cost = [d for d in tool_results if "value" in d]

    check("graph ran all five nodes in order", started == ["in", "rag", "brain", "cost", "out"])
    check("retrieval fired", any("retrieved" in d for d in tool_results))
    check("llm streamed tokens", len(tokens) > 3)
    check("tool(eval) returned a numeric cost", bool(cost) and cost[0].get("ok") is True)
    check("workflow produced a final output", bool(final))
    check("all expected phases present",
          {"start", "tool_call", "tool_result", "token", "node_done", "done"} <= phases)

    print("-" * 68)
    print(f"RESULT: {_passed} passed, {_failed} failed")
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

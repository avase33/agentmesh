"""CLI: ``agentmesh-intel run|serve``."""

from __future__ import annotations

import argparse
import asyncio
import sys

from .engine import AgentEngine
from .workflows import rag_cost_workflow


async def _run(input_text: str) -> int:
    engine = AgentEngine()
    print("=" * 68)
    print(f"agentmesh intelligence — llm={engine.llm.name} "
          f"executor={'rust' if engine.executor.remote else 'local'} "
          f"kb={len(engine.store)} docs")
    print("=" * 68)
    final = ""
    async for ev in engine.run("cli", rag_cost_workflow(), input_text):
        if ev.phase == "start":
            print(f"  ▶ {ev.node} ({ev.data.get('type')})")
        elif ev.phase == "tool_call":
            print(f"      · tool_call {ev.data}")
        elif ev.phase == "tool_result":
            print(f"      · tool_result {ev.data}")
        elif ev.phase == "node_done":
            snippet = ev.text if len(ev.text) < 80 else ev.text[:77] + "..."
            print(f"    ✓ {ev.node}: {snippet}")
        elif ev.phase == "done":
            final = ev.text
    print("-" * 68)
    print("FINAL:", final)
    return 0


def _serve(host: str, port: int) -> int:
    try:
        import uvicorn  # type: ignore
    except ImportError:
        print("Install server extras: pip install 'agentmesh-intelligence[server]'", file=sys.stderr)
        return 1
    uvicorn.run("agentmesh_intelligence.server:app", host=host, port=port, log_level="info")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="agentmesh-intel")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run the demo RAG+cost workflow offline")
    r.add_argument("--input", default="How does the Go gateway scale?")
    s = sub.add_parser("serve", help="run the FastAPI service")
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--port", type=int, default=8081)
    args = p.parse_args(argv)

    if args.cmd == "run":
        return asyncio.run(_run(args.input))
    return _serve(args.host, args.port)


if __name__ == "__main__":
    raise SystemExit(main())

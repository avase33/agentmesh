"""The agent engine — a LangGraph-style DAG executor.

Runs a :class:`Workflow` in topological order, threading each node's output to
its successors, and streams :class:`RunEvent` s as it goes. Node types:

* ``input``    seeds the graph with the user's message
* ``retrieve`` RAG lookup against the vector store
* ``llm``      streams a grounded answer (and asks the Rust executor to count
               tokens for a cost estimate)
* ``tool``     delegates ``eval`` / ``tokenize`` / ``csv`` to the Rust executor
* ``output``   collects the final result

The engine never blocks the event loop on compute — heavy work is handed to the
Rust layer (or its offline mirror).
"""

from __future__ import annotations

from typing import AsyncIterator, Optional

from .executor_client import ExecutorClient
from .llm import BaseLLM, build_llm
from .models import RunEvent, Workflow
from .rag import VectorStore, default_store


class AgentEngine:
    def __init__(
        self,
        executor: Optional[ExecutorClient] = None,
        llm: Optional[BaseLLM] = None,
        store: Optional[VectorStore] = None,
    ) -> None:
        self.executor = executor or ExecutorClient()
        self.llm = llm or build_llm()
        self.store = store or default_store()

    @staticmethod
    def _incoming(wf: Workflow, node_id: str, values: dict[str, str], seed: str) -> str:
        preds = [e.frm for e in wf.edges if e.to == node_id]
        if not preds:
            return seed
        return "\n".join(values.get(p, "") for p in preds).strip()

    async def run(
        self, run_id: str, workflow: Workflow, input_text: str
    ) -> AsyncIterator[RunEvent]:
        order = workflow.topo_order()
        values: dict[str, str] = {}
        variables: dict[str, float] = {}
        final = ""

        for nid in order:
            node = workflow.node(nid)
            assert node is not None
            incoming = self._incoming(workflow, nid, values, input_text)
            yield RunEvent(run_id, nid, "start", data={"type": node.type})
            out = incoming

            if node.type == "input":
                out = input_text

            elif node.type == "retrieve":
                k = int(node.config.get("k", 3))
                docs = self.store.retrieve(incoming or input_text, k)
                out = "\n".join(d.text for d in docs)
                yield RunEvent(run_id, nid, "tool_result", data={"retrieved": [d.id for d in docs]})

            elif node.type == "llm":
                system = node.config.get("system", "You are a helpful agent in the mesh.")
                tok = await self.executor.tokenize(incoming or input_text)
                variables["tokens"] = float(tok["count"])
                yield RunEvent(
                    run_id, nid, "tool_call",
                    data={"tool": "tokenize", "count": tok["count"], "engine": "rust" if self.executor.remote else "local"},
                )
                acc: list[str] = []
                async for piece in self.llm.stream(system, input_text, incoming):
                    acc.append(piece)
                    yield RunEvent(run_id, nid, "token", text=piece)
                out = "".join(acc).strip()

            elif node.type == "tool":
                tool = node.config.get("tool", "eval")
                yield RunEvent(run_id, nid, "tool_call", data={"tool": tool})
                if tool == "eval":
                    expr = node.config.get("expr", "tokens")
                    res = await self.executor.eval(expr, variables)
                    out = str(res.get("value"))
                    yield RunEvent(run_id, nid, "tool_result", data=res)
                elif tool == "tokenize":
                    res = await self.executor.tokenize(incoming or input_text)
                    variables["tokens"] = float(res["count"])
                    out = str(res["count"])
                    yield RunEvent(run_id, nid, "tool_result", data={"count": res["count"]})
                elif tool == "csv":
                    csv_text = node.config.get("csv", incoming)
                    op = node.config.get("op", "sum")
                    column = node.config.get("column", "")
                    res = await self.executor.csv(csv_text, op, column)
                    out = str(res.get("result"))
                    yield RunEvent(run_id, nid, "tool_result", data=res)

            elif node.type == "output":
                out = incoming
                final = incoming

            values[nid] = out
            preview = out if len(out) <= 400 else out[:397] + "..."
            yield RunEvent(run_id, nid, "node_done", text=preview)

        if not final and order:
            final = values.get(order[-1], "")
        yield RunEvent(run_id, "__end__", "done", text=final, data={"vars": variables})

    async def run_collect(self, run_id: str, workflow: Workflow, input_text: str):
        """Convenience for tests/CLI: returns (events, final_text)."""
        events = []
        final = ""
        async for ev in self.run(run_id, workflow, input_text):
            events.append(ev)
            if ev.phase == "done":
                final = ev.text
        return events, final

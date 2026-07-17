"""Shared data types mirroring proto/protocol.md."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Node:
    id: str
    type: str  # input | retrieve | llm | tool | output
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
    frm: str
    to: str


@dataclass
class Workflow:
    nodes: list[Node]
    edges: list[Edge]

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Workflow":
        nodes = [Node(n["id"], n["type"], n.get("config", {})) for n in d.get("nodes", [])]
        edges = [Edge(e["from"], e["to"]) for e in d.get("edges", [])]
        return Workflow(nodes=nodes, edges=edges)

    def node(self, node_id: str) -> Optional[Node]:
        return next((n for n in self.nodes if n.id == node_id), None)

    def successors(self, node_id: str) -> list[str]:
        return [e.to for e in self.edges if e.frm == node_id]

    def indegree(self) -> dict[str, int]:
        deg = {n.id: 0 for n in self.nodes}
        for e in self.edges:
            if e.to in deg:
                deg[e.to] += 1
        return deg

    def topo_order(self) -> list[str]:
        """Kahn's algorithm — raises on cycles."""
        deg = self.indegree()
        queue = [nid for nid, d in deg.items() if d == 0]
        order: list[str] = []
        while queue:
            nid = queue.pop(0)
            order.append(nid)
            for succ in self.successors(nid):
                deg[succ] -= 1
                if deg[succ] == 0:
                    queue.append(succ)
        if len(order) != len(self.nodes):
            raise ValueError("workflow graph has a cycle")
        return order


@dataclass
class RunEvent:
    run_id: str
    node: str
    phase: str  # start | token | tool_call | tool_result | node_done | done | error
    text: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "runId": self.run_id,
            "node": self.node,
            "phase": self.phase,
            "ts": self.ts,
        }
        if self.text:
            d["text"] = self.text
        if self.data:
            d["data"] = self.data
        return d

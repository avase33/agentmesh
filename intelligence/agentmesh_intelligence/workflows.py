"""Prebuilt example workflows."""

from __future__ import annotations

from .models import Workflow

# input -> retrieve (RAG) -> llm -> tool(eval: cost estimate) -> output
RAG_COST_WORKFLOW = {
    "nodes": [
        {"id": "in", "type": "input"},
        {"id": "rag", "type": "retrieve", "config": {"k": 3}},
        {"id": "brain", "type": "llm", "config": {"system": "You are an agent in the mesh."}},
        {"id": "cost", "type": "tool", "config": {"tool": "eval", "expr": "tokens * 0.000002"}},
        {"id": "out", "type": "output"},
    ],
    "edges": [
        {"from": "in", "to": "rag"},
        {"from": "rag", "to": "brain"},
        {"from": "brain", "to": "cost"},
        {"from": "cost", "to": "out"},
    ],
}


def rag_cost_workflow() -> Workflow:
    return Workflow.from_dict(RAG_COST_WORKFLOW)

"""A tiny in-memory retrieval store (RAG) with hashing embeddings.

No external vector DB and no ML dependency: documents are embedded into a
fixed-width bag-of-hashed-tokens vector and scored by cosine similarity. Enough
to demonstrate retrieval wiring; swap ``embed`` for a real model / Milvus client
in production.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

_DIM = 256
_WORD = re.compile(r"[a-z0-9]+")


def embed(text: str) -> list[float]:
    vec = [0.0] * _DIM
    for tok in _WORD.findall(text.lower()):
        vec[hash(tok) % _DIM] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


@dataclass
class Doc:
    id: str
    text: str
    vec: list[float]


class VectorStore:
    def __init__(self) -> None:
        self._docs: list[Doc] = []

    def add(self, doc_id: str, text: str) -> None:
        self._docs.append(Doc(doc_id, text, embed(text)))

    def retrieve(self, query: str, k: int = 3) -> list[Doc]:
        if not self._docs:
            return []
        q = embed(query)
        ranked = sorted(self._docs, key=lambda d: cosine(q, d.vec), reverse=True)
        return ranked[: max(1, k)]

    def __len__(self) -> int:
        return len(self._docs)


def default_store() -> VectorStore:
    """A small seeded knowledge base so retrieval nodes have something to find."""
    store = VectorStore()
    store.add(
        "arch-go",
        "The Go gateway handles authentication and tens of thousands of concurrent "
        "WebSocket connections using goroutines with low memory overhead.",
    )
    store.add(
        "arch-python",
        "The Python intelligence layer runs LangGraph-style agent state machines, "
        "formats prompts, calls LLM APIs, and performs vector retrieval for RAG.",
    )
    store.add(
        "arch-rust",
        "The Rust executor runs sandboxed evaluation, ultra-fast tokenization, and "
        "CSV aggregation with C-level speed and no garbage-collection pauses.",
    )
    store.add(
        "arch-ts",
        "The TypeScript/Next.js dashboard renders a drag-and-drop node canvas and "
        "streams live run events over WebSockets.",
    )
    return store

"""LLM provider abstraction with an offline, deterministic mock.

The mesh's "brain" streams tokens like a hosted model would, but the default
provider needs no API key: it composes a grounded answer from the user input and
any retrieved context. Swap in OpenAI/Anthropic via env without touching the
engine.
"""

from __future__ import annotations

import abc
import asyncio
import os
from typing import AsyncIterator


class BaseLLM(abc.ABC):
    name = "base"

    @abc.abstractmethod
    async def stream(self, system: str, user: str, context: str = "") -> AsyncIterator[str]:
        raise NotImplementedError
        yield  # pragma: no cover


class MockLLM(BaseLLM):
    name = "mock"

    def __init__(self, token_delay_s: float = 0.005) -> None:
        self.token_delay_s = token_delay_s

    async def stream(self, system: str, user: str, context: str = "") -> AsyncIterator[str]:
        reply = self._compose(system, user, context)
        for word in reply.split():
            await asyncio.sleep(self.token_delay_s)
            yield word + " "

    @staticmethod
    def _compose(system: str, user: str, context: str) -> str:
        parts: list[str] = []
        if context.strip():
            parts.append(
                f"Based on the retrieved context, here is what I found regarding "
                f"'{user.strip()}':"
            )
            snippet = context.strip().replace("\n", " ")
            if len(snippet) > 220:
                snippet = snippet[:217] + "..."
            parts.append(snippet)
        else:
            parts.append(f"You asked: {user.strip()}.")
            parts.append(
                "I can route this through retrieval, tool execution, and synthesis "
                "across the mesh to produce a grounded answer."
            )
        return " ".join(parts)


class OpenAILLM(BaseLLM):  # pragma: no cover - needs network + key
    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        from openai import AsyncOpenAI  # type: ignore

        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def stream(self, system: str, user: str, context: str = "") -> AsyncIterator[str]:
        content = user if not context else f"{user}\n\nContext:\n{context}"
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": content}],
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


def build_llm() -> BaseLLM:
    provider = os.environ.get("AGENTMESH_LLM", "mock").lower()
    if provider == "openai" and os.environ.get("OPENAI_API_KEY"):
        return OpenAILLM(os.environ["OPENAI_API_KEY"], os.environ.get("AGENTMESH_LLM_MODEL", "gpt-4o-mini"))
    return MockLLM()

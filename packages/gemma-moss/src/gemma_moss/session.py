#
# Copyright (c) 2025, InferEdge Inc.
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Conversational session layer composing Moss retrieval with Ollama/Gemma."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable, Awaitable
from dataclasses import dataclass, field
from typing import Optional

from ollama import AsyncClient

from .moss_retriever import MossRetriever

__all__ = ["GemmaMossSession"]

logger = logging.getLogger("gemma_moss")


@dataclass(frozen=True)
class _PreparedTurn:
    """Internal dataclass holding the assembled messages for one turn."""

    messages: list[dict[str, str]] = field(default_factory=list)


class GemmaMossSession:
    """Conversational session that composes Moss retrieval with Ollama/Gemma.

    Each call to :meth:`ask` or :meth:`ask_stream`:

    1. Optionally rewrites the user query for better retrieval.
    2. Retrieves relevant context from the Moss index.
    3. Assembles messages: ``[system, *history, context?, user]``.
    4. Sends to Ollama and returns the assistant response.
    5. Persists the raw user message and assistant reply in history
       (context is **not** persisted).

    Usage::

        session = GemmaMossSession(
            retriever=retriever,
            system_prompt="You are a helpful assistant.",
        )
        reply = await session.ask("What is Moss?")
    """

    def __init__(
        self,
        *,
        retriever: MossRetriever,
        model: str = "gemma4",
        ollama_host: str | None = None,
        system_prompt: str,
        query_rewriter: Callable[[str], Awaitable[str]] | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> None:
        """Initialize the session.

        Args:
            retriever: Moss retriever for fetching relevant context.
            model: Ollama model name to use for generation.
            ollama_host: Optional Ollama server host URL.
            system_prompt: System prompt prepended to every request.
            query_rewriter: Optional async callable that rewrites the user
                message into a better retrieval query.
            history: Optional initial conversation history (copied, not by ref).
        """
        self._retriever = retriever
        self._model = model
        self._system_prompt = system_prompt
        self._query_rewriter = query_rewriter
        self._history: list[dict[str, str]] = list(history) if history else []
        self._ollama = AsyncClient(host=ollama_host)

    async def ask(self, message: str) -> str:
        """Send a message and return the assistant response.

        Args:
            message: The user message.

        Returns:
            The assistant's response text.
        """
        prepared = await self._prepare_turn(message)
        response = await self._generate_text(prepared)
        self._commit_turn(message, response)
        return response

    async def ask_stream(self, message: str) -> AsyncIterator[str]:
        """Send a message and stream the assistant response token-by-token.

        Args:
            message: The user message.

        Yields:
            Response text chunks as they arrive.
        """
        prepared = await self._prepare_turn(message)
        accumulated: list[str] = []
        async for chunk in self._generate_stream(prepared):
            accumulated.append(chunk)
            yield chunk
        self._commit_turn(message, "".join(accumulated))

    def reset(self) -> None:
        """Clear the conversation history."""
        self._history.clear()

    def get_history(self) -> list[dict[str, str]]:
        """Return a copy of the conversation history.

        Returns:
            A shallow copy of the history list.
        """
        return list(self._history)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _prepare_turn(self, message: str) -> _PreparedTurn:
        """Resolve query, retrieve context, and build messages.

        Args:
            message: The raw user message.

        Returns:
            A ``_PreparedTurn`` containing the assembled message list.
        """
        query = await self._resolve_query(message)
        context = await self._resolve_context(query)
        messages = self._build_messages(message=message, context=context)
        return _PreparedTurn(messages=messages)

    async def _generate_text(self, prepared: _PreparedTurn) -> str:
        """Generate a complete response from Ollama.

        Args:
            prepared: The prepared turn with assembled messages.

        Returns:
            The assistant's full response text.
        """
        response = await self._ollama.chat(
            model=self._model,
            messages=prepared.messages,
            stream=False,
        )
        return response.message.content

    async def _generate_stream(self, prepared: _PreparedTurn) -> AsyncIterator[str]:
        """Stream response chunks from Ollama.

        Args:
            prepared: The prepared turn with assembled messages.

        Yields:
            Response text chunks.
        """
        stream = await self._ollama.chat(
            model=self._model,
            messages=prepared.messages,
            stream=True,
        )
        async for chunk in stream:
            yield chunk.message.content

    def _commit_turn(self, message: str, response: str) -> None:
        """Persist user message and assistant reply to history.

        Args:
            message: The original user message.
            response: The assistant's response.
        """
        self._history.append({"role": "user", "content": message})
        self._history.append({"role": "assistant", "content": response})

    async def _resolve_query(self, message: str) -> str:
        """Resolve the retrieval query using the rewriter or raw message.

        If a query rewriter is configured, it is called. On failure or empty
        result, the raw message is used as fallback.

        Args:
            message: The raw user message.

        Returns:
            The query string to use for retrieval.
        """
        if self._query_rewriter is not None:
            try:
                rewritten = await self._query_rewriter(message)
                if rewritten:
                    return rewritten
                logger.warning("Query rewriter returned empty string, using raw message")
            except Exception:
                logger.warning("Query rewriter failed, falling back to raw message", exc_info=True)
        return message

    async def _resolve_context(self, query: str) -> str | None:
        """Retrieve context from Moss, with graceful degradation.

        Args:
            query: The retrieval query.

        Returns:
            The formatted context string, or None if retrieval fails or
            returns no results.
        """
        try:
            return await self._retriever.retrieve(query)
        except Exception:
            logger.warning("Retrieval failed, continuing without context", exc_info=True)
            return None

    def _build_messages(
        self, *, message: str, context: str | None
    ) -> list[dict[str, str]]:
        """Assemble the message list for Ollama.

        Order: ``[system_prompt, *history, context (if any), user message]``.

        Args:
            message: The user message.
            context: The retrieved context, or None.

        Returns:
            The assembled message list.
        """
        messages: list[dict[str, str]] = [
            {"role": "system", "content": self._system_prompt},
        ]
        messages.extend(self._history)
        if context is not None:
            messages.append({"role": "system", "content": context})
        messages.append({"role": "user", "content": message})
        return messages

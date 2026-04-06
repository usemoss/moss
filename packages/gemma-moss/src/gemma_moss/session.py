#
# Copyright (c) 2025, InferEdge Inc.
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Chat session with Moss retrieval via Ollama tool calling."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Sequence

from ollama import AsyncClient

from .moss_retriever import MossRetriever

__all__ = ["GemmaMossSession"]

logger = logging.getLogger("gemma_moss")


def _build_tool_definition(description: str) -> dict:
    """Build the Ollama tool definition for Moss search."""
    return {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to find relevant information.",
                    },
                },
                "required": ["query"],
            },
        },
    }


class GemmaMossSession:
    """Chat session where Gemma decides when to query Moss via tool calling.

    Usage::

        retriever = MossRetriever(index_name="my-index")
        await retriever.load_index()

        session = GemmaMossSession(retriever=retriever)
        response = await session.ask("How do refunds work?")
    """

    def __init__(
        self,
        *,
        retriever: MossRetriever,
        model: str = "gemma4",
        ollama_host: str | None = None,
        system_prompt: str | None = None,
        index_description: str = "a knowledge base",
        history: Sequence[dict[str, str]] | None = None,
    ) -> None:
        """Initialize the session.

        Args:
            retriever: A ``MossRetriever`` instance (must have ``load_index()`` called).
            model: Ollama model name.
            ollama_host: Ollama server URL.
            system_prompt: Override the default system prompt. If ``None``, built
                from ``index_description``.
            index_description: What's in the Moss index (used in default prompt and
                tool description).
            history: Optional initial conversation history (copied on construction).
        """
        self._retriever = retriever
        self._model = model
        self._ollama = AsyncClient(host=ollama_host)
        self._history: list[dict] = list(history) if history else []
        self._tool = _build_tool_definition(
            f"Search {index_description} for relevant information."
        )
        self._system_prompt = system_prompt or (
            f"You are a helpful assistant with access to {index_description}. "
            "Use the search_knowledge_base tool when you need information from "
            "the knowledge base. Do not search for greetings or conversational replies."
        )

    async def ask(self, message: str) -> str:
        """Send a message and return the response.

        Gemma may call the Moss search tool, in which case the session executes
        the search and sends the results back for a final answer.
        """
        messages = self._build_messages(message)

        response = await self._ollama.chat(
            model=self._model,
            messages=messages,
            tools=[self._tool],
            stream=False,
        )

        # Handle tool call if Gemma wants to search
        if response.message.tool_calls:
            tool_call = response.message.tool_calls[0]
            query = tool_call.function.arguments.get("query", message)

            # Execute the Moss search
            tool_result = await self._execute_search(query)

            # Send tool result back to Gemma
            messages.append(response.message)
            messages.append({"role": "tool", "content": tool_result})

            response = await self._ollama.chat(
                model=self._model,
                messages=messages,
                stream=False,
            )

        result = response.message.content
        self._commit_turn(message, result)
        return result

    async def ask_stream(self, message: str) -> AsyncIterator[str]:
        """Send a message and yield the response.

        Calls ``ask()`` internally and yields the complete response.
        """
        response = await self.ask(message)
        yield response

    def reset(self) -> None:
        """Clear conversation history."""
        self._history.clear()

    def get_history(self) -> list[dict[str, str]]:
        """Return a copy of the conversation history."""
        return list(self._history)

    async def _execute_search(self, query: str) -> str:
        """Execute a Moss search and return formatted results."""
        try:
            result = await self._retriever.retrieve(query)
            if result is None:
                return "No relevant results found."
            return result
        except Exception:
            logger.warning("Moss search failed", exc_info=True)
            return "Search is currently unavailable."

    def _build_messages(self, message: str) -> list[dict]:
        """Assemble the message list."""
        messages: list[dict] = [
            {"role": "system", "content": self._system_prompt},
        ]
        messages.extend(self._history)
        messages.append({"role": "user", "content": message})
        return messages

    def _commit_turn(self, message: str, response: str) -> None:
        """Persist user + assistant turns to history."""
        self._history.append({"role": "user", "content": message})
        self._history.append({"role": "assistant", "content": response})

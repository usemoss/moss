"""
title: Moss Knowledge Base Search
description: Search a Moss semantic index. Gemma (or any model) can call this tool to retrieve relevant information.
author: InferEdge
version: 0.0.1
"""

import time

from pydantic import BaseModel, Field


class Tools:
    """Moss semantic search tool for Open WebUI with in-memory index."""

    class Valves(BaseModel):
        """Configuration — set these in Open WebUI's tool settings."""

        moss_project_id: str = Field(
            default="",
            description="Moss project ID (from portal.usemoss.dev)",
        )
        moss_project_key: str = Field(
            default="",
            description="Moss project key (from portal.usemoss.dev)",
        )
        moss_index_name: str = Field(
            default="",
            description="Name of the Moss index to search",
        )
        top_k: int = Field(
            default=5,
            description="Number of results to return per search",
        )
        alpha: float = Field(
            default=0.8,
            description="Blend: 1.0 = semantic only, 0.0 = keyword only",
        )

    def __init__(self):
        self.valves = self.Valves()
        self._client = None
        self._index_loaded = False

    def _ensure_client(self):
        """Lazy-init the Moss client."""
        if self._client is None:
            from inferedge_moss import MossClient

            self._client = MossClient(
                project_id=self.valves.moss_project_id,
                project_key=self.valves.moss_project_key,
            )

    async def _ensure_index(self):
        """Load the index into memory if not already loaded."""
        if not self._index_loaded:
            self._ensure_client()
            await self._client.load_index(self.valves.moss_index_name)
            await self._client.load_index(
                self.valves.moss_index_name, auto_refresh=True
            )
            self._index_loaded = True

    async def search_knowledge_base(
        self,
        query: str,
        __user__: dict = {},
        __event_emitter__=None,
    ) -> str:
        """Search the Moss knowledge base for relevant information.

        Use this tool when you need to look up facts, policies, documentation,
        or any information that might be in the knowledge base.

        :param query: The search query to find relevant information.
        :return: Relevant results from the knowledge base, or an error message.
        """
        if not self.valves.moss_project_id or not self.valves.moss_project_key:
            return "Error: Moss credentials not configured. Set them in the tool's Valves settings."

        if not self.valves.moss_index_name:
            return "Error: Moss index name not configured. Set it in the tool's Valves settings."

        try:
            # Emit status while loading/searching
            if __event_emitter__:
                if not self._index_loaded:
                    await __event_emitter__(
                        {
                            "type": "status",
                            "data": {
                                "description": f"Loading Moss index '{self.valves.moss_index_name}'...",
                                "done": False,
                            },
                        }
                    )

                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": f"Searching for: {query}",
                            "done": False,
                        },
                    }
                )

            await self._ensure_index()

            from inferedge_moss import QueryOptions

            start = time.perf_counter()
            result = await self._client.query(
                self.valves.moss_index_name,
                query,
                options=QueryOptions(
                    top_k=self.valves.top_k, alpha=self.valves.alpha
                ),
            )
            elapsed_ms = (time.perf_counter() - start) * 1000

            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": f"Moss: {len(result.docs)} results in {elapsed_ms:.1f}ms",
                            "done": True,
                        },
                    }
                )

            if not result.docs:
                return "No relevant results found."

            lines = [f"Relevant results ({len(result.docs)} found in {elapsed_ms:.1f}ms):\n"]
            for i, doc in enumerate(result.docs, 1):
                text = getattr(doc, "text", "") or ""
                score = getattr(doc, "score", None)
                meta = getattr(doc, "metadata", None) or {}
                source = meta.get("source", "")

                extras = []
                if source:
                    extras.append(f"source={source}")
                if score is not None:
                    extras.append(f"score={score:.3f}")
                suffix = f" ({', '.join(extras)})" if extras else ""
                lines.append(f"{i}. {text}{suffix}")

            return "\n".join(lines)

        except Exception as e:
            self._index_loaded = False
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": f"Search failed: {e}", "done": True},
                    }
                )
            return f"Search failed: {str(e)}"

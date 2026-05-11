"""
Multi-tenant index routing with Moss.

Each business gets its own named Moss index. At query time the agent uses
LangChain tool calling to pick which index (or indexes) to search. Indexes
load lazily on first use — only the ones actually called pay the load cost.
"""
from __future__ import annotations

from langchain_core.tools import StructuredTool
from moss import MossClient, QueryOptions
from pydantic import BaseModel, Field


class IndexStore:
    """
    Lazy-loading registry of named Moss indexes.

    Each index is loaded from the Moss cloud on its first query and kept
    resident in memory for subsequent calls. Multiple indexes can be queried
    independently — LangChain's AgentExecutor handles parallelism.

    Usage::

        store = IndexStore(client, top_k=5)
        result = await store.search("food-luigis-pizzeria", "vegan options?")
    """

    def __init__(self, client: MossClient, top_k: int = 5, alpha: float = 0.5) -> None:
        self._client = client
        self.top_k = top_k
        self.alpha = alpha
        self._loaded: set[str] = set()

    async def search(self, index_name: str, query: str) -> str:
        """
        Query a named index and return a formatted context string.

        Loads the index on first call. Subsequent calls on the same index
        skip the load step and return in <10ms.
        """
        if index_name not in self._loaded:
            await self._client.load_index(index_name)
            self._loaded.add(index_name)

        results = await self._client.query(
            index_name,
            query,
            QueryOptions(top_k=self.top_k, alpha=self.alpha),
        )

        if not results.docs:
            return "No relevant information found in this index."

        return "\n\n".join(f"[{i}] {doc.text}" for i, doc in enumerate(results.docs, 1))


class _SearchInput(BaseModel):
    query: str = Field(description="Search query to run against this business's knowledge base.")


def build_tools(index_configs: dict[str, dict[str, str]], store: IndexStore) -> list[StructuredTool]:
    """
    Build LangChain StructuredTools from index configs + a shared IndexStore.

    Each index becomes one tool. The tool name is derived from the index name
    (hyphens → underscores, prefixed with `search_`) so the model can identify
    the business from the name alone. The description tells the model what each
    index covers to enable accurate routing.

    Returns a list ready to pass to `create_tool_calling_agent` or `bind_tools`.
    """
    tools = []
    for index_name, config in index_configs.items():
        tool_name = "search_" + index_name.replace("-", "_")

        # Capture index_name to avoid the loop late-binding gotcha
        def _make_coroutine(idx: str):
            async def _run(query: str) -> str:
                return await store.search(idx, query)
            return _run

        tools.append(
            StructuredTool.from_function(
                name=tool_name,
                description=config["tool_description"],
                args_schema=_SearchInput,
                coroutine=_make_coroutine(index_name),
            )
        )
    return tools

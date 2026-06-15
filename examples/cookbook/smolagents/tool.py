import asyncio
import threading
from typing import Any, Dict, Optional

from smolagents import Tool
from moss import MossClient, QueryOptions


class MossRetrievalTool(Tool):
    """Smolagents Tool that runs semantic search against a locally loaded Moss index."""

    name = "moss_retrieval"
    description = (
        "Finds relevant information from a knowledge base using semantic search. "
        "Use this when the answer is likely contained in indexed documents."
    )
    inputs = {
        "query": {
            "type": "string",
            "description": "The search query string.",
        },
        "top_k": {
            "type": "integer",
            "description": "Number of results to return (default: 5).",
            "nullable": True,
            "default": 5,
        },
        "metadata_filter": {
            "type": "object",
            "description": (
                "Optional filter using the Moss filter DSL. "
                "Example: {'$and': [{'field': 'category', 'condition': {'$eq': 'refunds'}}]}"
            ),
            "nullable": True,
        },
    }
    output_type = "string"

    def __init__(self, client: MossClient, index_name: str):
        super().__init__()
        self.client = client
        self.index_name = index_name
        # A persistent event loop in a daemon thread avoids two problems:
        # 1. Per-call loop creation/teardown overhead (kills sub-10ms latency).
        # 2. RuntimeError when forward() is called from an already-running loop
        #    (Jupyter notebooks, async frameworks).
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()

    def _run_async(self, coro) -> Any:
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result()

    def forward(
        self,
        query: str,
        top_k: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> str:
        options = QueryOptions(top_k=top_k, filter=metadata_filter)
        results = self._run_async(self.client.query(self.index_name, query, options))
        return "\n\n".join(
            f"--- Result ID: {doc.id} (Score: {doc.score:.3f}) ---\n{doc.text}"
            for doc in results.docs
        )

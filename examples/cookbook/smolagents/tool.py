import asyncio
from typing import Any, Dict, Optional
from smolagents import Tool
from inferedge_moss import MossClient, QueryOptions

class MossRetrievalTool(Tool):
    """
    A custom tool for smolagents that performs semantic search using Moss.
    """
    name = "moss_retrieval"
    description = (
        "Finds relevant information from the company's internal documentation "
        "using semantic search. Useful for answering specific questions where "
        "the answer is likely in the knowledge base."
    )
    inputs = {
        "query": {
            "type": "string",
            "description": "The search query string.",
        },
        "top_k": {
            "type": "integer",
            "description": "The number of results to return.",
            "nullable": True,
        },
        "metadata_filter": {
            "type": "object",
            "description": (
                "Optional metadata filter using Moss structured filter DSL. "
                "Example: {'operator': 'AND', 'conditions': [{'field': 'category', 'operator': 'eq', 'value': 'refunds'}]}"
            ),
            "nullable": True,
        },
    }
    output_type = "string"

    def __init__(self, client: MossClient, index_name: str):
        super().__init__()
        self.client = client
        self.index_name = index_name

    def forward(self, query: str, top_k: int = 5, metadata_filter: Optional[Dict[str, Any]] = None) -> str:
        """
        Executes the search via the Moss client using an asyncio-to-sync bridge.
        """
        options = QueryOptions(
            top_k=top_k,
            filter=metadata_filter
        )
        
        try:
            results = asyncio.run(self.client.query(self.index_name, query, options))
        except RuntimeError as e:
            if "asyncio.run() cannot be called from a running event loop" in str(e):
                raise RuntimeError(
                    "MossRetrievalTool.forward() cannot be called from a running event loop (e.g., in a Jupyter notebook). "
                    "This is a known limitation of the current smolagents synchronous tool design."
                ) from e
            raise e

        # Format results so the agent can easily read them
        output = [f"--- Result ID: {doc.id} (Score: {doc.score:.3f}) ---\n{doc.text}\n" for doc in results.docs]
        return "\n".join(output)

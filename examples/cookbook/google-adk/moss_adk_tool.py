from typing import Any, Dict, Optional

from moss import MossClient, QueryOptions


def create_moss_tool(client: MossClient, index_name: str):
    """
    Factory function that creates a Google ADK compatible asynchronous tool
    for Moss semantic retrieval.
    """

    async def moss_retrieval(
        query: str,
        top_k: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Finds relevant information from a knowledge base using semantic search.
        Use this when the answer is likely contained in indexed documents.

        Args:
            query: The search query string.
            top_k: Number of results to return (default: 5).
            metadata_filter: Optional filter using the Moss filter DSL.
                             Example: {'$and': [{'field': 'category', 'condition': {'$eq': 'refunds'}}]}
        """
        options = QueryOptions(top_k=top_k, filter=metadata_filter)
        results = await client.query(index_name, query, options)

        if not results.docs:
            return "No relevant information found."

        return "\n\n".join(
            f"--- Result ID: {doc.id} (Score: {doc.score:.3f}) ---\n{doc.text}"
            for doc in results.docs
        )

    return moss_retrieval

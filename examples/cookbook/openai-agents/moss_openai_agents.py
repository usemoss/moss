"""Moss retrieval tools for the OpenAI Agents SDK.

Wraps MossClient.query() as @function_tool callables so any OpenAI Agents SDK
agent can perform semantic search, manage documents, and inspect indexes.
"""

import asyncio
import uuid
from typing import Any

from agents import RunContextWrapper, function_tool
from moss import DocumentInfo, GetDocumentsOptions, MossClient, MutationOptions, QueryOptions


def moss_search_tool(client: MossClient, index_name: str, top_k: int = 5, alpha: float = 0.8):
    """Create a Moss semantic search tool bound to a specific index.

    Args:
        client: Shared MossClient instance.
        index_name: Index to search.
        top_k: Number of results to return.
        alpha: Hybrid search balance (0=keyword, 1=semantic).
    """
    _index_loaded = False

    @function_tool(name_override="moss_search")
    async def moss_search(query: str) -> str:
        """Search a knowledge base using Moss semantic search. Returns the most relevant documents for a given query.

        Args:
            query: The search query text.
        """
        nonlocal _index_loaded
        if not _index_loaded:
            await client.load_index(index_name)
            _index_loaded = True

        results = await client.query(
            index_name,
            query,
            QueryOptions(top_k=top_k, alpha=alpha),
        )
        if not results.docs:
            return "No relevant information found."
        return "\n\n".join(
            f"Result {i + 1} (score: {doc.score:.2f}):\n{doc.text}"
            for i, doc in enumerate(results.docs)
        )

    return moss_search


def moss_search_with_filter_tool(
    client: MossClient, index_name: str, top_k: int = 5, alpha: float = 0.8
):
    """Create a Moss search tool that supports optional metadata filters.

    Args:
        client: Shared MossClient instance.
        index_name: Index to search.
        top_k: Number of results to return.
        alpha: Hybrid search balance (0=keyword, 1=semantic).
    """
    _index_loaded = False

    @function_tool(name_override="moss_search_with_filter")
    async def moss_search_with_filter(
        query: str,
        filter_field: str | None = None,
        filter_value: str | None = None,
    ) -> str:
        """Search a knowledge base with optional metadata filtering.

        Args:
            query: The search query text.
            filter_field: Optional metadata field name to filter on (e.g. 'country').
            filter_value: Value the filter_field must match (e.g. 'Japan').
        """
        nonlocal _index_loaded
        if not _index_loaded:
            await client.load_index(index_name)
            _index_loaded = True

        opts = QueryOptions(top_k=top_k, alpha=alpha)
        if filter_field and filter_value:
            opts = QueryOptions(
                top_k=top_k,
                alpha=alpha,
                filter={filter_field: filter_value},
            )

        results = await client.query(index_name, query, opts)
        if not results.docs:
            return "No relevant information found."
        return "\n\n".join(
            f"Result {i + 1} (score: {doc.score:.2f}):\n{doc.text}"
            for i, doc in enumerate(results.docs)
        )

    return moss_search_with_filter


def moss_add_docs_tool(client: MossClient, index_name: str):
    """Create a tool to add documents to a Moss index.

    Args:
        client: Shared MossClient instance.
        index_name: Index to add documents to.
    """

    @function_tool(name_override="moss_add_docs")
    async def moss_add_docs(texts: list[str], ids: list[str] | None = None, upsert: bool = False) -> str:
        """Add text documents to a Moss semantic search index.

        Args:
            texts: List of text documents to add.
            ids: Optional document IDs (auto-generated if omitted).
            upsert: If True, update existing documents with the same ID.
        """
        doc_ids = ids or [str(uuid.uuid4()) for _ in texts]
        docs = [DocumentInfo(id=did, text=text) for did, text in zip(doc_ids, texts)]
        options = MutationOptions(upsert=upsert)
        await client.add_docs(index_name, docs, options)
        return f"Added {len(docs)} document(s) to '{index_name}'."

    return moss_add_docs


def moss_get_docs_tool(client: MossClient, index_name: str):
    """Create a tool to retrieve documents from a Moss index.

    Args:
        client: Shared MossClient instance.
        index_name: Index to retrieve from.
    """

    @function_tool(name_override="moss_get_docs")
    async def moss_get_docs(doc_ids: list[str] | None = None) -> str:
        """Retrieve documents from a Moss index. Fetches all if no IDs provided.

        Args:
            doc_ids: Optional list of document IDs to retrieve.
        """
        options = GetDocumentsOptions(ids=doc_ids) if doc_ids else GetDocumentsOptions()
        result = await client.get_docs(index_name, options)
        if not result.docs:
            return "No documents found."
        return "\n\n".join(
            f"[{doc.id}]: {doc.text[:200]}{'...' if len(doc.text) > 200 else ''}"
            for doc in result.docs
        )

    return moss_get_docs


def moss_delete_docs_tool(client: MossClient, index_name: str):
    """Create a tool to delete documents from a Moss index.

    Args:
        client: Shared MossClient instance.
        index_name: Index to delete from.
    """

    @function_tool(name_override="moss_delete_docs")
    async def moss_delete_docs(doc_ids: list[str]) -> str:
        """Delete specific documents from a Moss index by their IDs.

        Args:
            doc_ids: List of document IDs to delete.
        """
        await client.delete_docs(index_name, doc_ids)
        return f"Deleted {len(doc_ids)} document(s) from '{index_name}'."

    return moss_delete_docs


def moss_list_indexes_tool(client: MossClient):
    """Create a tool to list all Moss indexes.

    Args:
        client: Shared MossClient instance.
    """

    @function_tool(name_override="moss_list_indexes")
    async def moss_list_indexes() -> str:
        """List all indexes with document counts and status."""
        indexes = await client.list_indexes()
        if not indexes:
            return "No indexes found."
        return "\n".join(
            f"- {idx.name}: {idx.doc_count} docs ({idx.status})"
            for idx in indexes
        )

    return moss_list_indexes


def moss_tools(
    client: MossClient,
    index_name: str,
    top_k: int = 5,
    alpha: float = 0.8,
) -> list:
    """Create all Moss tools with shared configuration.

    Args:
        client: Shared MossClient instance.
        index_name: Default index for tools that operate on a single index.
        top_k: Number of search results.
        alpha: Hybrid search balance.

    Returns:
        List of function tools ready to pass to an Agent.
    """
    return [
        moss_search_tool(client, index_name, top_k, alpha),
        moss_search_with_filter_tool(client, index_name, top_k, alpha),
        moss_add_docs_tool(client, index_name),
        moss_get_docs_tool(client, index_name),
        moss_delete_docs_tool(client, index_name),
        moss_list_indexes_tool(client),
    ]

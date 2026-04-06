"""Moss semantic search integration with Gemma via Ollama."""

from inferedge_moss import (
    DocumentInfo,
    GetDocumentsOptions,
    IndexInfo,
    MossClient,
    SearchResult,
)

from .formatters import DefaultContextFormatter
from .moss_retriever import MossRetriever
from .session import GemmaMossSession, make_ollama_query_rewriter

__all__ = [
    "MossRetriever",
    "GemmaMossSession",
    "DefaultContextFormatter",
    "make_ollama_query_rewriter",
    # Re-exports from inferedge_moss
    "MossClient",
    "SearchResult",
    "DocumentInfo",
    "IndexInfo",
    "GetDocumentsOptions",
]

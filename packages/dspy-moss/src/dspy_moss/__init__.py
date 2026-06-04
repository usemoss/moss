"""Moss semantic search retrieval module for DSPy."""

from __future__ import annotations

from moss import (
    DocumentInfo,
    GetDocumentsOptions,
    IndexInfo,
    MossClient,
    SearchResult,
)

from .retrieve import MossRM

__all__ = [
    "DocumentInfo",
    "GetDocumentsOptions",
    "IndexInfo",
    "MossClient",
    "MossRM",
    "SearchResult",
]

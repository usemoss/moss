"""Moss vector database integration for Pipecat."""

from __future__ import annotations

from inferedge_moss import (
    AddDocumentsOptions,
    DocumentInfo,
    GetDocumentsOptions,
    IndexInfo,
    MossClient,
    SearchResult,
)

from .moss_retrieval_service import MossRetrievalService

__all__ = [
    "AddDocumentsOptions",
    "DocumentInfo",
    "GetDocumentsOptions",
    "IndexInfo",
    "MossClient",
    "MossRetrievalService",
    "SearchResult",
]

"""Shared fixtures and helpers for moss-cli tests."""

from __future__ import annotations

import json
import types
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock

import pytest
from typer.testing import CliRunner

from moss_cli.main import app


@pytest.fixture
def runner() -> CliRunner:
    """CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def mock_client() -> Mock:
    """Pre-configured mock MossClient with AsyncMock methods."""
    client = Mock()
    client.list_indexes = AsyncMock(return_value=[])
    client.get_index = AsyncMock()
    client.create_index = AsyncMock()
    client.delete_index = AsyncMock(return_value=True)
    client.add_docs = AsyncMock()
    client.delete_docs = AsyncMock()
    client.get_docs = AsyncMock(return_value=[])
    client.get_job_status = AsyncMock()
    client.query = AsyncMock()
    client.load_index = AsyncMock()
    return client


def parse_json(output: str) -> Any:
    """Parse JSON from CLI output, stripping trailing whitespace."""
    return json.loads(output.strip())


def make_model(model_id: str = "moss-minilm", version: str = "1.0.0") -> types.SimpleNamespace:
    """Create a mock model object."""
    return types.SimpleNamespace(id=model_id, version=version)


def make_index(
    name: str = "test-index",
    index_id: str = "idx_123",
    status: str = "Ready",
    doc_count: int = 100,
    version: int = 1,
    model_id: str = "moss-minilm",
    created_at: str = "2026-04-10T00:00:00Z",
    updated_at: str = "2026-04-10T00:00:00Z",
) -> types.SimpleNamespace:
    """Create a mock IndexInfo object."""
    return types.SimpleNamespace(
        id=index_id,
        name=name,
        version=version,
        status=status,
        doc_count=doc_count,
        created_at=created_at,
        updated_at=updated_at,
        model=make_model(model_id),
    )


def make_doc(
    doc_id: str = "doc-1",
    text: str = "Hello world",
    metadata: Dict[str, str] | None = None,
    embedding: List[float] | None = None,
) -> types.SimpleNamespace:
    """Create a mock DocumentInfo object."""
    return types.SimpleNamespace(
        id=doc_id,
        text=text,
        metadata=metadata,
        embedding=embedding,
    )


def make_result_doc(
    doc_id: str = "doc-1",
    text: str = "Hello world",
    score: float = 0.95,
    metadata: Dict[str, str] | None = None,
) -> types.SimpleNamespace:
    """Create a mock search result document."""
    return types.SimpleNamespace(
        id=doc_id,
        text=text,
        score=score,
        metadata=metadata,
    )


def make_search_result(
    query: str = "test query",
    index_name: str = "test-index",
    time_taken_ms: int = 42,
    docs: List[Any] | None = None,
) -> types.SimpleNamespace:
    """Create a mock SearchResult object."""
    return types.SimpleNamespace(
        query=query,
        index_name=index_name,
        time_taken_ms=time_taken_ms,
        docs=docs or [make_result_doc()],
    )


def make_mutation_result(
    job_id: str = "job_123",
    index_name: str = "test-index",
    doc_count: int = 10,
) -> types.SimpleNamespace:
    """Create a mock MutationResult object."""
    return types.SimpleNamespace(
        job_id=job_id,
        index_name=index_name,
        doc_count=doc_count,
    )


def make_job_status(
    job_id: str = "job_123",
    status: str = "COMPLETED",
    progress: float = 100.0,
    created_at: str = "2026-04-10T00:00:00Z",
    updated_at: str = "2026-04-10T00:00:00Z",
    completed_at: str = "2026-04-10T00:01:00Z",
    current_phase: str | None = None,
    error: str | None = None,
) -> types.SimpleNamespace:
    """Create a mock JobStatus object."""
    ns = types.SimpleNamespace(
        job_id=job_id,
        status=types.SimpleNamespace(value=status),
        progress=progress,
        created_at=created_at,
        updated_at=updated_at,
        completed_at=completed_at,
        error=error,
    )
    if current_phase:
        ns.current_phase = types.SimpleNamespace(value=current_phase)
    else:
        ns.current_phase = None
    return ns

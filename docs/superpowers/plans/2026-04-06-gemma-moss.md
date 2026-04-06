# Gemma + Moss Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python package (`gemma-moss`) that integrates Moss semantic retrieval with Gemma via Ollama, using a 3-layer architecture: `MossRetriever`, optional `QueryRewriter`, and `GemmaMossSession`.

**Architecture:** Three layers with clear separation — retriever owns Moss access, session owns chat/history, rewriter is an optional callable injected into the session. `ask()` and `ask_stream()` share a single internal turn pipeline split into prepare/generate/commit phases.

**Tech Stack:** Python 3.10+, inferedge-moss SDK, ollama Python SDK, pytest, ruff

**Spec:** `docs/superpowers/specs/2026-04-06-gemma-moss-integration-design.md`

---

## File Map

| File | Responsibility |
|------|---------------|
| `packages/gemma-moss/src/gemma_moss/__init__.py` | Public API exports |
| `packages/gemma-moss/src/gemma_moss/formatters.py` | `DefaultContextFormatter` |
| `packages/gemma-moss/src/gemma_moss/moss_retriever.py` | `MossRetriever` — Moss client wrapper |
| `packages/gemma-moss/src/gemma_moss/session.py` | `GemmaMossSession` — chat session with RAG |
| `packages/gemma-moss/tests/test_formatters.py` | Formatter tests |
| `packages/gemma-moss/tests/test_moss_retriever.py` | Retriever tests (mocked Moss) |
| `packages/gemma-moss/tests/test_session.py` | Session tests (mocked retriever + Ollama) |
| `packages/gemma-moss/examples/moss-gemma-demo.py` | CLI chatbot demo |
| `packages/gemma-moss/examples/moss-create-index-demo.py` | Index setup helper |
| `packages/gemma-moss/pyproject.toml` | Package config |
| `packages/gemma-moss/README.md` | Documentation |
| `packages/gemma-moss/CONTRIBUTING.md` | Dev setup guide |
| `packages/gemma-moss/CHANGELOG.md` | Release notes |
| `packages/gemma-moss/LICENSE` | BSD 2-Clause |

---

### Task 1: Scaffold the package

**Files:**
- Create: `packages/gemma-moss/pyproject.toml`
- Create: `packages/gemma-moss/src/gemma_moss/__init__.py`
- Create: `packages/gemma-moss/LICENSE`
- Create: `packages/gemma-moss/CHANGELOG.md`
- Create: `packages/gemma-moss/CONTRIBUTING.md`
- Create: `packages/gemma-moss/README.md`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p packages/gemma-moss/src/gemma_moss
mkdir -p packages/gemma-moss/tests
mkdir -p packages/gemma-moss/examples
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[project]
name = "gemma-moss"
version = "0.0.1"
description = "Moss semantic search integration with Gemma via Ollama"
readme = "README.md"
requires-python = ">=3.10,<3.14"
dependencies = [
    "inferedge-moss>=1.0.0b18",
    "ollama>=0.4.0",
]

[dependency-groups]
dev = [
    "python-dotenv>=1.2.1",
    "ruff>=0.1.0",
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = [
    "E",  # pycodestyle errors
    "W",  # pycodestyle warnings
    "F",  # pyflakes
    "I",  # isort
    "B",  # flake8-bugbear
    "UP", # pyupgrade
    "D",  # pydocstyle
]
ignore = [
    "D100", # Missing docstring in public module
    "D104", # Missing docstring in public package
]

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
skip-magic-trailing-comma = false
line-ending = "auto"

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
namespaces = false

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 3: Create placeholder `__init__.py`**

```python
"""Moss semantic search integration with Gemma via Ollama."""
```

- [ ] **Step 4: Create `LICENSE`**

Copy the BSD 2-Clause license text from `packages/elevenlabs-moss/LICENSE` verbatim.

- [ ] **Step 5: Create `CHANGELOG.md`**

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.1] - 2026-04-06

### Added

- Initial release of `gemma-moss` integration.
- `MossRetriever` for reusable Moss semantic retrieval.
- `GemmaMossSession` for conversational RAG with Gemma via Ollama.
- `DefaultContextFormatter` for formatting retrieved documents.
- `make_ollama_query_rewriter` convenience helper.
- CLI chatbot demo in `examples/moss-gemma-demo.py`.
```

- [ ] **Step 6: Create `CONTRIBUTING.md`**

```markdown
# Contributing

Thanks for your interest in improving Gemma Moss! This document captures the
workflow for working from the source repository.

## Development Environment

1. Clone the repository and `cd` into it.
2. Install dependencies using [uv](https://github.com/astral-sh/uv):

   ```bash
   uv sync
   ```

3. Activate the virtual environment so local scripts (examples, tests) run
   against the checked-out code:

   ```bash
   source .venv/bin/activate
   ```

## Running Examples

With the environment active you can run the sample scripts shipped in the
[examples](examples) directory. Please refer to the [README](README.md) for detailed instructions on running the examples.

## Code Style

Follow the existing formatting and logging patterns in the codebase.

## Submitting Changes

1. Open a pull request that describes the motivation, highlights user-facing
   changes, and includes validation steps.
2. Be responsive to review feedback so the change can merge smoothly.

We appreciate your contributions!
```

- [ ] **Step 7: Create stub `README.md`**

```markdown
# Gemma Moss Integration

Moss delivers sub-10ms semantic retrieval for your Gemma-powered chatbot running locally via Ollama.

> Full documentation will be added after implementation is complete.
```

- [ ] **Step 8: Verify structure and commit**

```bash
cd packages/gemma-moss
find . -type f | sort
```

Expected: all files listed above present.

```bash
cd ../..
git add packages/gemma-moss/
git commit -m "scaffold: gemma-moss package structure"
```

---

### Task 2: Implement `DefaultContextFormatter`

**Files:**
- Create: `packages/gemma-moss/src/gemma_moss/formatters.py`
- Create: `packages/gemma-moss/tests/test_formatters.py`

- [ ] **Step 1: Write failing tests for `DefaultContextFormatter`**

Create `packages/gemma-moss/tests/test_formatters.py`:

```python
"""Tests for DefaultContextFormatter."""

from unittest.mock import MagicMock

from gemma_moss.formatters import DefaultContextFormatter


class TestDefaultContextFormatter:
    """Tests for DefaultContextFormatter."""

    def test_returns_none_for_empty_list(self):
        """Return None when given an empty document list."""
        formatter = DefaultContextFormatter()
        assert formatter([]) is None

    def test_formats_single_document(self):
        """Format a single document with text only."""
        doc = MagicMock()
        doc.text = "How to track your order"
        doc.metadata = {}
        doc.score = None

        formatter = DefaultContextFormatter()
        result = formatter([doc])

        assert result is not None
        assert "1. How to track your order" in result
        assert result.startswith("Relevant context from knowledge base:")

    def test_formats_multiple_documents_with_metadata(self):
        """Format multiple documents with source and score metadata."""
        doc1 = MagicMock()
        doc1.text = "Return policy info"
        doc1.metadata = {"source": "faq.md"}
        doc1.score = 0.95

        doc2 = MagicMock()
        doc2.text = "Shipping details"
        doc2.metadata = {"source": "shipping.md"}
        doc2.score = 0.87

        formatter = DefaultContextFormatter()
        result = formatter([doc1, doc2])

        assert result is not None
        assert "1. Return policy info" in result
        assert "source=faq.md" in result
        assert "score=0.95" in result
        assert "2. Shipping details" in result

    def test_custom_prefix(self):
        """Use a custom prefix."""
        doc = MagicMock()
        doc.text = "Test document"
        doc.metadata = {}
        doc.score = None

        formatter = DefaultContextFormatter(prefix="Custom prefix:\n\n")
        result = formatter([doc])

        assert result is not None
        assert result.startswith("Custom prefix:")

    def test_handles_missing_text(self):
        """Handle document with None text gracefully."""
        doc = MagicMock()
        doc.text = None
        doc.metadata = {}
        doc.score = None

        formatter = DefaultContextFormatter()
        result = formatter([doc])

        assert result is not None
        assert "1. " in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd packages/gemma-moss && uv sync && uv run pytest tests/test_formatters.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'gemma_moss.formatters'`

- [ ] **Step 3: Implement `DefaultContextFormatter`**

Create `packages/gemma-moss/src/gemma_moss/formatters.py`:

```python
#
# Copyright (c) 2025, InferEdge Inc.
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Context formatting helpers for Moss search results."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

__all__ = ["DefaultContextFormatter"]


class DefaultContextFormatter:
    """Format Moss search results into a context string for LLM consumption.

    Usage::

        formatter = DefaultContextFormatter(prefix="Context:\\n\\n")
        text = formatter(documents)  # str | None
    """

    def __init__(
        self,
        *,
        prefix: str = "Relevant context from knowledge base:\n\n",
    ) -> None:
        """Initialize with a prefix for the formatted output.

        Args:
            prefix: Text prepended to the formatted document list.
        """
        self._prefix = prefix

    def __call__(self, documents: Sequence[Any]) -> str | None:
        """Format documents into a numbered context string.

        Args:
            documents: Sequence of Moss document objects with `text`, `metadata`,
                and optionally `score` attributes.

        Returns:
            Formatted string, or None if the document list is empty.
        """
        if not documents:
            return None

        lines = [self._prefix.rstrip(), ""]
        for idx, doc in enumerate(documents, start=1):
            text = getattr(doc, "text", "") or ""
            meta = getattr(doc, "metadata", None) or {}
            extras = []

            if source := meta.get("source"):
                extras.append(f"source={source}")
            if (score := getattr(doc, "score", None)) is not None:
                extras.append(f"score={score}")

            suffix = f" ({', '.join(extras)})" if extras else ""
            lines.append(f"{idx}. {text}{suffix}")

        return "\n".join(lines).strip()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd packages/gemma-moss && uv run pytest tests/test_formatters.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd ../..
git add packages/gemma-moss/src/gemma_moss/formatters.py packages/gemma-moss/tests/test_formatters.py
git commit -m "feat: add DefaultContextFormatter with tests"
```

---

### Task 3: Implement `MossRetriever`

**Files:**
- Create: `packages/gemma-moss/src/gemma_moss/moss_retriever.py`
- Create: `packages/gemma-moss/tests/test_moss_retriever.py`

- [ ] **Step 1: Write failing tests for `MossRetriever`**

Create `packages/gemma-moss/tests/test_moss_retriever.py`:

```python
"""Tests for MossRetriever."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gemma_moss.moss_retriever import MossRetriever


class TestMossRetriever:
    """Tests for MossRetriever."""

    def _make_retriever(self, **kwargs) -> MossRetriever:
        """Create a retriever with mocked MossClient."""
        defaults = {
            "project_id": "test-project",
            "project_key": "test-key",
            "index_name": "test-index",
        }
        defaults.update(kwargs)
        with patch("gemma_moss.moss_retriever.MossClient"):
            return MossRetriever(**defaults)

    @pytest.mark.asyncio
    async def test_query_before_load_raises(self):
        """Raise RuntimeError if query is called before load_index."""
        retriever = self._make_retriever()
        with pytest.raises(RuntimeError, match="not loaded"):
            await retriever.query("test query")

    @pytest.mark.asyncio
    async def test_retrieve_before_load_raises(self):
        """Raise RuntimeError if retrieve is called before load_index."""
        retriever = self._make_retriever()
        with pytest.raises(RuntimeError, match="not loaded"):
            await retriever.retrieve("test query")

    @pytest.mark.asyncio
    async def test_load_index(self):
        """Load index delegates to MossClient."""
        retriever = self._make_retriever()
        retriever._client.load_index = AsyncMock()

        await retriever.load_index()

        retriever._client.load_index.assert_awaited_once_with("test-index")

    @pytest.mark.asyncio
    async def test_query_returns_search_result(self):
        """Query returns raw SearchResult from MossClient."""
        retriever = self._make_retriever()
        retriever._index_loaded = True

        mock_result = MagicMock()
        mock_result.docs = []
        retriever._client.query = AsyncMock(return_value=mock_result)

        result = await retriever.query("test query")

        assert result is mock_result
        retriever._client.query.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_retrieve_returns_formatted_string(self):
        """Retrieve returns formatted string from the formatter."""
        doc = MagicMock()
        doc.text = "Test document"
        doc.metadata = {}
        doc.score = 0.9

        mock_result = MagicMock()
        mock_result.docs = [doc]

        retriever = self._make_retriever()
        retriever._index_loaded = True
        retriever._client.query = AsyncMock(return_value=mock_result)

        result = await retriever.retrieve("test query")

        assert result is not None
        assert "Test document" in result

    @pytest.mark.asyncio
    async def test_retrieve_returns_none_for_empty_results(self):
        """Retrieve returns None when no documents match."""
        mock_result = MagicMock()
        mock_result.docs = []

        retriever = self._make_retriever()
        retriever._index_loaded = True
        retriever._client.query = AsyncMock(return_value=mock_result)

        result = await retriever.retrieve("test query")

        assert result is None

    @pytest.mark.asyncio
    async def test_custom_formatter(self):
        """Retrieve uses a custom formatter when provided."""
        doc = MagicMock()
        doc.text = "Hello"
        doc.metadata = {}

        mock_result = MagicMock()
        mock_result.docs = [doc]

        custom_formatter = MagicMock(return_value="custom output")

        retriever = self._make_retriever(formatter=custom_formatter)
        retriever._index_loaded = True
        retriever._client.query = AsyncMock(return_value=mock_result)

        result = await retriever.retrieve("test query")

        assert result == "custom output"
        custom_formatter.assert_called_once_with([doc])

    @pytest.mark.asyncio
    async def test_custom_top_k_and_alpha(self):
        """Query passes top_k and alpha to MossClient."""
        retriever = self._make_retriever(top_k=3, alpha=0.5)
        retriever._index_loaded = True

        mock_result = MagicMock()
        mock_result.docs = []
        retriever._client.query = AsyncMock(return_value=mock_result)

        await retriever.query("test")

        call_args = retriever._client.query.call_args
        options = call_args[1].get("options") or call_args[0][2] if len(call_args[0]) > 2 else call_args[1].get("options")
        assert options.top_k == 3
        assert options.alpha == 0.5
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd packages/gemma-moss && uv run pytest tests/test_moss_retriever.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'gemma_moss.moss_retriever'`

- [ ] **Step 3: Implement `MossRetriever`**

Create `packages/gemma-moss/src/gemma_moss/moss_retriever.py`:

```python
#
# Copyright (c) 2025, InferEdge Inc.
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Moss retrieval adapter for semantic search."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import Any, Optional

from inferedge_moss import MossClient, QueryOptions, SearchResult

from .formatters import DefaultContextFormatter

__all__ = ["MossRetriever"]

logger = logging.getLogger("gemma_moss")


class MossRetriever:
    """Thin reusable retrieval adapter over the Moss SDK.

    Usage::

        retriever = MossRetriever(index_name="my-index")
        await retriever.load_index()

        # Raw search
        result = await retriever.query("search terms")

        # Formatted for LLM context
        context = await retriever.retrieve("search terms")
    """

    def __init__(
        self,
        *,
        project_id: str | None = None,
        project_key: str | None = None,
        index_name: str,
        top_k: int = 5,
        alpha: float = 0.8,
        formatter: Callable[[Sequence[Any]], str | None] | None = None,
    ) -> None:
        """Initialize the retriever.

        Args:
            project_id: Moss project ID. Falls back to ``MOSS_PROJECT_ID`` env var.
            project_key: Moss project key. Falls back to ``MOSS_PROJECT_KEY`` env var.
            index_name: Name of the Moss index to query.
            top_k: Number of results to retrieve per query.
            alpha: Blend between semantic (1.0) and keyword (0.0) scoring.
            formatter: Optional callable to format docs into context. Defaults to
                ``DefaultContextFormatter``.
        """
        self._client = MossClient(project_id=project_id, project_key=project_key)
        self._index_name = index_name
        self._top_k = top_k
        self._alpha = alpha
        self._formatter = formatter or DefaultContextFormatter()
        self._index_loaded = False

    async def load_index(self) -> None:
        """Pre-load the Moss index into memory for fast queries."""
        logger.info("Loading Moss index '%s'", self._index_name)
        await self._client.load_index(self._index_name)
        self._index_loaded = True
        logger.info("Moss index '%s' ready", self._index_name)

    async def query(self, query: str) -> SearchResult:
        """Perform a raw semantic search against the Moss index.

        Args:
            query: The search query text.

        Returns:
            Raw ``SearchResult`` from the Moss SDK.

        Raises:
            RuntimeError: If ``load_index()`` has not been called.
        """
        self._ensure_loaded()
        return await self._client.query(
            self._index_name,
            query,
            options=QueryOptions(top_k=self._top_k, alpha=self._alpha),
        )

    async def retrieve(self, query: str) -> str | None:
        """Search and format results into an LLM-ready context string.

        Args:
            query: The search query text.

        Returns:
            Formatted context string, or ``None`` if no documents matched.

        Raises:
            RuntimeError: If ``load_index()`` has not been called.
        """
        result = await self.query(query)
        return self._formatter(result.docs)

    def _ensure_loaded(self) -> None:
        """Raise if the index has not been loaded."""
        if not self._index_loaded:
            raise RuntimeError(
                f"Index '{self._index_name}' not loaded. Call await load_index() first."
            )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd packages/gemma-moss && uv run pytest tests/test_moss_retriever.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd ../..
git add packages/gemma-moss/src/gemma_moss/moss_retriever.py packages/gemma-moss/tests/test_moss_retriever.py
git commit -m "feat: add MossRetriever with tests"
```

---

### Task 4: Implement `GemmaMossSession`

**Files:**
- Create: `packages/gemma-moss/src/gemma_moss/session.py`
- Create: `packages/gemma-moss/tests/test_session.py`

- [ ] **Step 1: Write failing tests for `GemmaMossSession`**

Create `packages/gemma-moss/tests/test_session.py`:

```python
"""Tests for GemmaMossSession."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gemma_moss.session import GemmaMossSession


def _mock_retriever(context: str | None = "Mocked context") -> MagicMock:
    """Create a mocked MossRetriever."""
    retriever = MagicMock()
    retriever.retrieve = AsyncMock(return_value=context)
    return retriever


class TestGemmaMossSession:
    """Tests for GemmaMossSession."""

    @pytest.mark.asyncio
    async def test_ask_returns_response(self):
        """ask() returns the full response string."""
        retriever = _mock_retriever()

        with patch("gemma_moss.session.AsyncClient") as MockOllama:
            mock_client = MagicMock()
            mock_client.chat = AsyncMock(return_value=MagicMock(
                message=MagicMock(content="Test response")
            ))
            MockOllama.return_value = mock_client

            session = GemmaMossSession(retriever=retriever, model="gemma4")
            result = await session.ask("Hello")

        assert result == "Test response"

    @pytest.mark.asyncio
    async def test_ask_persists_history(self):
        """ask() adds user and assistant turns to history."""
        retriever = _mock_retriever()

        with patch("gemma_moss.session.AsyncClient") as MockOllama:
            mock_client = MagicMock()
            mock_client.chat = AsyncMock(return_value=MagicMock(
                message=MagicMock(content="Response 1")
            ))
            MockOllama.return_value = mock_client

            session = GemmaMossSession(retriever=retriever, model="gemma4")
            await session.ask("Question 1")

        history = session.get_history()
        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "Question 1"}
        assert history[1] == {"role": "assistant", "content": "Response 1"}

    @pytest.mark.asyncio
    async def test_context_not_persisted_in_history(self):
        """Retrieved context is ephemeral and not stored in history."""
        retriever = _mock_retriever(context="Secret context")

        with patch("gemma_moss.session.AsyncClient") as MockOllama:
            mock_client = MagicMock()
            mock_client.chat = AsyncMock(return_value=MagicMock(
                message=MagicMock(content="Answer")
            ))
            MockOllama.return_value = mock_client

            session = GemmaMossSession(retriever=retriever, model="gemma4")
            await session.ask("Question")

        history = session.get_history()
        for turn in history:
            assert "Secret context" not in turn["content"]

    @pytest.mark.asyncio
    async def test_ask_without_retrieval_context(self):
        """ask() works when retriever returns None."""
        retriever = _mock_retriever(context=None)

        with patch("gemma_moss.session.AsyncClient") as MockOllama:
            mock_client = MagicMock()
            mock_client.chat = AsyncMock(return_value=MagicMock(
                message=MagicMock(content="No context response")
            ))
            MockOllama.return_value = mock_client

            session = GemmaMossSession(retriever=retriever, model="gemma4")
            result = await session.ask("Hello")

        assert result == "No context response"

    @pytest.mark.asyncio
    async def test_ask_with_query_rewriter(self):
        """ask() uses the query rewriter to refine the search query."""
        retriever = _mock_retriever()
        rewriter = AsyncMock(return_value="refined query")

        with patch("gemma_moss.session.AsyncClient") as MockOllama:
            mock_client = MagicMock()
            mock_client.chat = AsyncMock(return_value=MagicMock(
                message=MagicMock(content="Answer")
            ))
            MockOllama.return_value = mock_client

            session = GemmaMossSession(
                retriever=retriever,
                model="gemma4",
                query_rewriter=rewriter,
            )
            await session.ask("What about returns?")

        rewriter.assert_awaited_once()
        retriever.retrieve.assert_awaited_once_with("refined query")

    @pytest.mark.asyncio
    async def test_rewriter_failure_falls_back_to_raw_message(self):
        """If rewriter raises, fall back to the raw user message."""
        retriever = _mock_retriever()
        rewriter = AsyncMock(side_effect=RuntimeError("rewriter broke"))

        with patch("gemma_moss.session.AsyncClient") as MockOllama:
            mock_client = MagicMock()
            mock_client.chat = AsyncMock(return_value=MagicMock(
                message=MagicMock(content="Fallback answer")
            ))
            MockOllama.return_value = mock_client

            session = GemmaMossSession(
                retriever=retriever,
                model="gemma4",
                query_rewriter=rewriter,
            )
            result = await session.ask("My question")

        assert result == "Fallback answer"
        retriever.retrieve.assert_awaited_once_with("My question")

    @pytest.mark.asyncio
    async def test_rewriter_empty_string_falls_back(self):
        """If rewriter returns empty string, fall back to raw message."""
        retriever = _mock_retriever()
        rewriter = AsyncMock(return_value="")

        with patch("gemma_moss.session.AsyncClient") as MockOllama:
            mock_client = MagicMock()
            mock_client.chat = AsyncMock(return_value=MagicMock(
                message=MagicMock(content="Answer")
            ))
            MockOllama.return_value = mock_client

            session = GemmaMossSession(
                retriever=retriever,
                model="gemma4",
                query_rewriter=rewriter,
            )
            await session.ask("Original question")

        retriever.retrieve.assert_awaited_once_with("Original question")

    @pytest.mark.asyncio
    async def test_retrieval_failure_continues_without_context(self):
        """If retriever.retrieve raises, continue generation without context."""
        retriever = MagicMock()
        retriever.retrieve = AsyncMock(side_effect=RuntimeError("Moss down"))

        with patch("gemma_moss.session.AsyncClient") as MockOllama:
            mock_client = MagicMock()
            mock_client.chat = AsyncMock(return_value=MagicMock(
                message=MagicMock(content="Answered without context")
            ))
            MockOllama.return_value = mock_client

            session = GemmaMossSession(retriever=retriever, model="gemma4")
            result = await session.ask("Hello")

        assert result == "Answered without context"

    @pytest.mark.asyncio
    async def test_reset_clears_history(self):
        """reset() empties conversation history."""
        retriever = _mock_retriever()

        with patch("gemma_moss.session.AsyncClient") as MockOllama:
            mock_client = MagicMock()
            mock_client.chat = AsyncMock(return_value=MagicMock(
                message=MagicMock(content="Response")
            ))
            MockOllama.return_value = mock_client

            session = GemmaMossSession(retriever=retriever, model="gemma4")
            await session.ask("Question")
            assert len(session.get_history()) == 2

            session.reset()
            assert len(session.get_history()) == 0

    @pytest.mark.asyncio
    async def test_get_history_returns_copy(self):
        """get_history() returns a copy, not a mutable reference."""
        retriever = _mock_retriever()

        with patch("gemma_moss.session.AsyncClient") as MockOllama:
            mock_client = MagicMock()
            mock_client.chat = AsyncMock(return_value=MagicMock(
                message=MagicMock(content="Response")
            ))
            MockOllama.return_value = mock_client

            session = GemmaMossSession(retriever=retriever, model="gemma4")
            await session.ask("Question")

        history = session.get_history()
        history.clear()
        assert len(session.get_history()) == 2

    @pytest.mark.asyncio
    async def test_initial_history_is_copied(self):
        """Constructor copies initial history, does not store by reference."""
        retriever = _mock_retriever()
        initial = [{"role": "user", "content": "Prior"}, {"role": "assistant", "content": "Reply"}]

        with patch("gemma_moss.session.AsyncClient"):
            session = GemmaMossSession(
                retriever=retriever, model="gemma4", history=initial
            )

        initial.clear()
        assert len(session.get_history()) == 2

    @pytest.mark.asyncio
    async def test_message_assembly_order(self):
        """Messages are assembled in the correct order: system, history, context, user."""
        retriever = _mock_retriever(context="Retrieved context")
        sent_messages = None

        with patch("gemma_moss.session.AsyncClient") as MockOllama:
            mock_client = MagicMock()

            async def capture_chat(**kwargs):
                nonlocal sent_messages
                sent_messages = kwargs.get("messages")
                return MagicMock(message=MagicMock(content="Answer"))

            mock_client.chat = capture_chat
            MockOllama.return_value = mock_client

            session = GemmaMossSession(
                retriever=retriever,
                model="gemma4",
                system_prompt="System prompt",
            )
            await session.ask("User question")

        assert sent_messages is not None
        assert sent_messages[0] == {"role": "system", "content": "System prompt"}
        assert sent_messages[-2] == {"role": "system", "content": "Retrieved context"}
        assert sent_messages[-1] == {"role": "user", "content": "User question"}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd packages/gemma-moss && uv run pytest tests/test_session.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'gemma_moss.session'`

- [ ] **Step 3: Implement `GemmaMossSession`**

Create `packages/gemma-moss/src/gemma_moss/session.py`:

```python
#
# Copyright (c) 2025, InferEdge Inc.
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Chat session with Moss retrieval-augmented generation via Ollama."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

from ollama import AsyncClient

from .moss_retriever import MossRetriever

__all__ = ["GemmaMossSession"]

logger = logging.getLogger("gemma_moss")

_DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful assistant. Use the provided context to answer questions accurately."
)


@dataclass(frozen=True)
class _PreparedTurn:
    """Internal: holds the assembled message list for an Ollama call."""

    messages: list[dict[str, str]]


class GemmaMossSession:
    """Conversational RAG session using Moss retrieval and Ollama.

    Usage::

        retriever = MossRetriever(index_name="my-index")
        await retriever.load_index()

        session = GemmaMossSession(retriever=retriever, model="gemma4")
        response = await session.ask("How do refunds work?")

        async for chunk in session.ask_stream("Tell me more"):
            print(chunk, end="")
    """

    def __init__(
        self,
        *,
        retriever: MossRetriever,
        model: str = "gemma4",
        ollama_host: str | None = None,
        system_prompt: str = _DEFAULT_SYSTEM_PROMPT,
        query_rewriter: Callable[[str, Sequence[dict[str, str]]], Awaitable[str]] | None = None,
        history: Sequence[dict[str, str]] | None = None,
    ) -> None:
        """Initialize the session.

        Args:
            retriever: A ``MossRetriever`` instance (must have ``load_index()`` called).
            model: Ollama model name.
            ollama_host: Ollama server URL. Defaults to ``http://localhost:11434``.
            system_prompt: Fixed system prompt for the conversation.
            query_rewriter: Optional async callable that rewrites user messages into
                better retrieval queries. Signature: ``(message, history) -> query``.
            history: Optional initial conversation history (copied on construction).
        """
        self._retriever = retriever
        self._model = model
        self._ollama = AsyncClient(host=ollama_host)
        self._system_prompt = system_prompt
        self._query_rewriter = query_rewriter
        self._history: list[dict[str, str]] = list(history) if history else []

    async def ask(self, message: str) -> str:
        """Send a message and return the full response.

        Args:
            message: The user's message.

        Returns:
            The assistant's complete response.
        """
        prepared = await self._prepare_turn(message)
        response = await self._generate_text(prepared)
        self._commit_turn(message, response)
        return response

    async def ask_stream(self, message: str) -> AsyncIterator[str]:
        """Send a message and stream the response token by token.

        Args:
            message: The user's message.

        Yields:
            Response text chunks as they arrive.
        """
        prepared = await self._prepare_turn(message)
        full_response = []

        async for chunk in self._generate_stream(prepared):
            full_response.append(chunk)
            yield chunk

        self._commit_turn(message, "".join(full_response))

    def reset(self) -> None:
        """Clear conversation history."""
        self._history.clear()

    def get_history(self) -> list[dict[str, str]]:
        """Return a copy of the conversation history.

        Returns:
            List of message dicts with ``role`` and ``content`` keys.
        """
        return list(self._history)

    # -- Internal turn pipeline ----------------------------------------

    async def _prepare_turn(self, message: str) -> _PreparedTurn:
        """Resolve query, retrieve context, build messages."""
        query = await self._resolve_query(message)
        context = await self._resolve_context(query)
        messages = self._build_messages(message=message, context=context)
        return _PreparedTurn(messages=messages)

    async def _generate_text(self, prepared: _PreparedTurn) -> str:
        """Generate a full response from Ollama."""
        response = await self._ollama.chat(
            model=self._model,
            messages=prepared.messages,
            stream=False,
        )
        return response.message.content

    async def _generate_stream(self, prepared: _PreparedTurn) -> AsyncIterator[str]:
        """Stream response chunks from Ollama."""
        stream = await self._ollama.chat(
            model=self._model,
            messages=prepared.messages,
            stream=True,
        )
        async for chunk in stream:
            content = chunk.message.content
            if content:
                yield content

    def _commit_turn(self, message: str, response: str) -> None:
        """Persist user and assistant turns to history."""
        self._history.append({"role": "user", "content": message})
        self._history.append({"role": "assistant", "content": response})

    async def _resolve_query(self, message: str) -> str:
        """Use rewriter if available, fall back to raw message."""
        if self._query_rewriter is None:
            return message

        try:
            rewritten = await self._query_rewriter(message, self._history)
            if rewritten and rewritten.strip():
                return rewritten.strip()
            logger.warning("Query rewriter returned empty; using raw message")
            return message
        except Exception:
            logger.warning("Query rewriter failed; using raw message", exc_info=True)
            return message

    async def _resolve_context(self, query: str) -> str | None:
        """Retrieve context from Moss, or None on failure."""
        try:
            return await self._retriever.retrieve(query)
        except Exception:
            logger.warning("Retrieval failed; continuing without context", exc_info=True)
            return None

    def _build_messages(
        self,
        *,
        message: str,
        context: str | None,
    ) -> list[dict[str, str]]:
        """Assemble the message list for Ollama."""
        messages: list[dict[str, str]] = [
            {"role": "system", "content": self._system_prompt},
        ]
        messages.extend(self._history)
        if context is not None:
            messages.append({"role": "system", "content": context})
        messages.append({"role": "user", "content": message})
        return messages
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd packages/gemma-moss && uv run pytest tests/test_session.py -v
```

Expected: all 12 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd ../..
git add packages/gemma-moss/src/gemma_moss/session.py packages/gemma-moss/tests/test_session.py
git commit -m "feat: add GemmaMossSession with tests"
```

---

### Task 5: Implement `make_ollama_query_rewriter` and wire up `__init__.py`

**Files:**
- Modify: `packages/gemma-moss/src/gemma_moss/session.py` (add the factory function)
- Modify: `packages/gemma-moss/src/gemma_moss/__init__.py` (wire up exports)
- Create: `packages/gemma-moss/tests/test_query_rewriter.py`

- [ ] **Step 1: Write failing tests for `make_ollama_query_rewriter`**

Create `packages/gemma-moss/tests/test_query_rewriter.py`:

```python
"""Tests for make_ollama_query_rewriter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gemma_moss.session import make_ollama_query_rewriter


class TestMakeOllamaQueryRewriter:
    """Tests for the Ollama query rewriter factory."""

    @pytest.mark.asyncio
    async def test_returns_rewritten_query(self):
        """Rewriter calls Ollama and returns the response content."""
        with patch("gemma_moss.session.AsyncClient") as MockOllama:
            mock_client = MagicMock()
            mock_client.chat = AsyncMock(return_value=MagicMock(
                message=MagicMock(content="  refined search query  ")
            ))
            MockOllama.return_value = mock_client

            rewriter = make_ollama_query_rewriter(model="gemma4")
            result = await rewriter("what about their refund policy?", [
                {"role": "user", "content": "Tell me about Acme Corp"},
                {"role": "assistant", "content": "Acme Corp is a retailer..."},
            ])

        assert result == "refined search query"

    @pytest.mark.asyncio
    async def test_includes_history_in_messages(self):
        """Rewriter sends conversation history to Ollama for context."""
        sent_messages = None

        with patch("gemma_moss.session.AsyncClient") as MockOllama:
            mock_client = MagicMock()

            async def capture_chat(**kwargs):
                nonlocal sent_messages
                sent_messages = kwargs.get("messages")
                return MagicMock(message=MagicMock(content="query"))

            mock_client.chat = capture_chat
            MockOllama.return_value = mock_client

            history = [{"role": "user", "content": "Prior turn"}]
            rewriter = make_ollama_query_rewriter(model="gemma4")
            await rewriter("current message", history)

        assert sent_messages is not None
        assert sent_messages[0]["role"] == "system"
        assert {"role": "user", "content": "Prior turn"} in sent_messages
        assert sent_messages[-1] == {"role": "user", "content": "current message"}

    @pytest.mark.asyncio
    async def test_custom_instruction(self):
        """Rewriter uses a custom instruction as the system prompt."""
        sent_messages = None

        with patch("gemma_moss.session.AsyncClient") as MockOllama:
            mock_client = MagicMock()

            async def capture_chat(**kwargs):
                nonlocal sent_messages
                sent_messages = kwargs.get("messages")
                return MagicMock(message=MagicMock(content="query"))

            mock_client.chat = capture_chat
            MockOllama.return_value = mock_client

            rewriter = make_ollama_query_rewriter(
                model="gemma4", instruction="Custom instruction"
            )
            await rewriter("message", [])

        assert sent_messages[0]["content"] == "Custom instruction"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd packages/gemma-moss && uv run pytest tests/test_query_rewriter.py -v
```

Expected: FAIL — `ImportError: cannot import name 'make_ollama_query_rewriter'`

- [ ] **Step 3: Add `make_ollama_query_rewriter` to `session.py`**

Append to the end of `packages/gemma-moss/src/gemma_moss/session.py`:

```python
_DEFAULT_REWRITER_INSTRUCTION = (
    "Based on the conversation history and the user's latest message, "
    "generate a concise, specific search query that would retrieve the most "
    "relevant information from a knowledge base. Output ONLY the search query, "
    "nothing else."
)


def make_ollama_query_rewriter(
    *,
    model: str = "gemma4",
    host: str | None = None,
    instruction: str = _DEFAULT_REWRITER_INSTRUCTION,
) -> Callable[[str, Sequence[dict[str, str]]], Awaitable[str]]:
    """Create an Ollama-powered query rewriter.

    This is a convenience helper, not part of the core architecture.
    Any async callable with signature ``(message, history) -> str`` works.

    Args:
        model: Ollama model name.
        host: Ollama server URL.
        instruction: System instruction for the rewriter model.

    Returns:
        An async callable that rewrites user messages into search queries.
    """
    client = AsyncClient(host=host)

    async def rewrite(message: str, history: Sequence[dict[str, str]]) -> str:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": instruction},
        ]
        messages.extend(history)
        messages.append({"role": "user", "content": message})

        response = await client.chat(model=model, messages=messages, stream=False)
        return response.message.content.strip()

    return rewrite
```

Also update `__all__` in `session.py`:

```python
__all__ = ["GemmaMossSession", "make_ollama_query_rewriter"]
```

- [ ] **Step 4: Wire up `__init__.py`**

Replace `packages/gemma-moss/src/gemma_moss/__init__.py`:

```python
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
```

- [ ] **Step 5: Run all tests**

```bash
cd packages/gemma-moss && uv run pytest tests/ -v
```

Expected: all tests PASS (formatters: 5, retriever: 8, session: 12, rewriter: 3 = 28 total).

- [ ] **Step 6: Run ruff**

```bash
cd packages/gemma-moss && uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/
```

Expected: no errors.

- [ ] **Step 7: Commit**

```bash
cd ../..
git add packages/gemma-moss/src/gemma_moss/ packages/gemma-moss/tests/test_query_rewriter.py
git commit -m "feat: add make_ollama_query_rewriter and wire up public API"
```

---

### Task 6: Create examples

**Files:**
- Create: `packages/gemma-moss/examples/moss-create-index-demo.py`
- Create: `packages/gemma-moss/examples/moss-gemma-demo.py`

- [ ] **Step 1: Create `moss-create-index-demo.py`**

Create `packages/gemma-moss/examples/moss-create-index-demo.py`:

```python
"""One-time setup: create a Moss index with sample FAQ documents.

Prerequisites:
    pip install gemma-moss python-dotenv

Environment variables:
    MOSS_PROJECT_ID, MOSS_PROJECT_KEY, MOSS_INDEX_NAME
"""

import asyncio
import os

from dotenv import load_dotenv

from gemma_moss import DocumentInfo, MossClient

load_dotenv()


async def main():
    """Create a sample FAQ index in Moss."""
    client = MossClient(
        project_id=os.getenv("MOSS_PROJECT_ID"),
        project_key=os.getenv("MOSS_PROJECT_KEY"),
    )

    documents = [
        DocumentInfo(
            id="doc-1",
            text=(
                "How do I track my order? You can track your order by logging into "
                "your account and visiting the 'Order History' section. Each order has "
                "a unique tracking number that you can use to monitor its delivery status."
            ),
            metadata={"category": "orders", "source": "faq"},
        ),
        DocumentInfo(
            id="doc-2",
            text=(
                "What is your return policy? We offer a 30-day return policy for most "
                "items. Products must be unused and in their original packaging. Return "
                "shipping costs may apply unless the item is defective."
            ),
            metadata={"category": "returns", "source": "faq"},
        ),
        DocumentInfo(
            id="doc-3",
            text=(
                "How can I change my shipping address? You can change your shipping "
                "address before order dispatch by contacting our customer service team. "
                "Once an order is dispatched, the shipping address cannot be modified."
            ),
            metadata={"category": "shipping", "source": "faq"},
        ),
        DocumentInfo(
            id="doc-4",
            text=(
                "Do you ship internationally? Yes, we ship to most countries worldwide. "
                "International shipping costs and delivery times vary by location. You "
                "can check shipping rates during checkout."
            ),
            metadata={"category": "shipping", "source": "faq"},
        ),
        DocumentInfo(
            id="doc-5",
            text=(
                "What payment methods do you accept? We accept Visa, Mastercard, "
                "American Express, PayPal, and Apple Pay. All payments are processed "
                "securely through our encrypted payment system."
            ),
            metadata={"category": "payment", "source": "faq"},
        ),
        DocumentInfo(
            id="doc-6",
            text=(
                "How long does shipping take? Standard domestic shipping typically "
                "takes 3-5 business days. Express shipping (1-2 business days) is "
                "available for most locations at an additional cost."
            ),
            metadata={"category": "shipping", "source": "faq"},
        ),
        DocumentInfo(
            id="doc-7",
            text=(
                "Can I cancel my order? Orders can be cancelled within 1 hour of "
                "placement. After that, if the order has not been shipped, you may "
                "contact customer service to request cancellation."
            ),
            metadata={"category": "orders", "source": "faq"},
        ),
        DocumentInfo(
            id="doc-8",
            text=(
                "What is your price match policy? We match prices from authorized "
                "retailers for identical items within 14 days of purchase. Send us "
                "proof of the lower price, and we'll refund the difference."
            ),
            metadata={"category": "pricing", "source": "faq"},
        ),
    ]

    print(f"Creating index '{os.getenv('MOSS_INDEX_NAME')}' with {len(documents)} documents...")
    result = await client.create_index(
        name=os.getenv("MOSS_INDEX_NAME"),
        docs=documents,
        model_id="moss-minilm",
    )
    print(f"Index created. Job ID: {result.job_id}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Create `moss-gemma-demo.py`**

Create `packages/gemma-moss/examples/moss-gemma-demo.py`:

```python
"""Interactive CLI chatbot: Gemma + Moss retrieval-augmented generation.

Prerequisites:
    pip install gemma-moss python-dotenv
    ollama pull gemma4

Environment variables:
    MOSS_PROJECT_ID, MOSS_PROJECT_KEY, MOSS_INDEX_NAME
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

from gemma_moss import GemmaMossSession, MossRetriever
from gemma_moss.session import make_ollama_query_rewriter

load_dotenv()


async def main():
    """Run the interactive chatbot."""
    # Validate environment
    required = ["MOSS_PROJECT_ID", "MOSS_PROJECT_KEY", "MOSS_INDEX_NAME"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        print(f"Missing environment variables: {', '.join(missing)}")
        print("Set them in a .env file or export them.")
        sys.exit(1)

    model = os.getenv("OLLAMA_MODEL", "gemma4")
    index_name = os.getenv("MOSS_INDEX_NAME")

    # Check Ollama is reachable
    try:
        from ollama import AsyncClient

        client = AsyncClient()
        await client.show(model)
    except Exception as e:
        print(f"Cannot reach Ollama or model '{model}' not found: {e}")
        print(f"Make sure Ollama is running and run: ollama pull {model}")
        sys.exit(1)

    # Set up retriever
    retriever = MossRetriever(
        project_id=os.getenv("MOSS_PROJECT_ID"),
        project_key=os.getenv("MOSS_PROJECT_KEY"),
        index_name=index_name,
    )
    print(f"Loading Moss index '{index_name}'...")
    await retriever.load_index()

    # Set up session with query rewriter
    session = GemmaMossSession(
        retriever=retriever,
        model=model,
        query_rewriter=make_ollama_query_rewriter(model=model),
    )

    print(f"\nGemma + Moss Chat (model: {model}, index: {index_name})")
    print("Commands: /reset (clear history), /quit (exit)\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input == "/quit":
            print("Goodbye!")
            break
        if user_input == "/reset":
            session.reset()
            print("History cleared.\n")
            continue

        print("Assistant: ", end="", flush=True)
        async for chunk in session.ask_stream(user_input):
            print(chunk, end="", flush=True)
        print("\n")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: Commit**

```bash
cd ../..
git add packages/gemma-moss/examples/
git commit -m "feat: add CLI chatbot and index setup examples"
```

---

### Task 7: Write full README

**Files:**
- Modify: `packages/gemma-moss/README.md`

- [ ] **Step 1: Write `README.md`**

Replace `packages/gemma-moss/README.md` with:

```markdown
# Gemma Moss Integration

Moss delivers sub-10ms semantic retrieval for your Gemma-powered chatbot running locally via Ollama.

## Installation

```bash
pip install gemma-moss
```

## Prerequisites

- Moss project ID and project key (get them from [Moss Portal](https://portal.usemoss.dev))
- [Ollama](https://ollama.com/) installed with the Gemma model pulled:

  ```bash
  ollama pull gemma4
  ```

## Quick Start

```python
import asyncio
import os
from gemma_moss import GemmaMossSession, MossRetriever
from gemma_moss.session import make_ollama_query_rewriter

async def main():
    # Set up retriever
    retriever = MossRetriever(
        project_id=os.getenv("MOSS_PROJECT_ID"),
        project_key=os.getenv("MOSS_PROJECT_KEY"),
        index_name="my-index",
    )
    await retriever.load_index()

    # Set up session (query rewriter is optional)
    session = GemmaMossSession(
        retriever=retriever,
        model="gemma4",
        query_rewriter=make_ollama_query_rewriter(model="gemma4"),
    )

    # Ask a question
    response = await session.ask("How do refunds work?")
    print(response)

    # Or stream the response
    async for chunk in session.ask_stream("Tell me more"):
        print(chunk, end="")

asyncio.run(main())
```

## Architecture

The package is split into three layers:

### MossRetriever

Reusable retrieval adapter over the Moss SDK. Can be used independently of the session.

```python
retriever = MossRetriever(index_name="my-index")
await retriever.load_index()

# Raw search result
result = await retriever.query("search terms")

# Formatted for LLM context
context = await retriever.retrieve("search terms")
```

### Query Rewriter (Optional)

Any async callable with signature `(message, history) -> str` can serve as a query rewriter. A convenience helper is provided:

```python
from gemma_moss.session import make_ollama_query_rewriter

rewriter = make_ollama_query_rewriter(model="gemma4")
```

### GemmaMossSession

Chat session that composes the retriever and optional rewriter.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `retriever` | (required) | A `MossRetriever` instance |
| `model` | `gemma4` | Ollama model name |
| `ollama_host` | `None` | Ollama server URL |
| `system_prompt` | (see source) | Fixed system prompt |
| `query_rewriter` | `None` | Optional query rewriter callable |
| `history` | `None` | Initial conversation history |

| Method | Description |
|--------|-------------|
| `ask(message)` | Send a message, return full response |
| `ask_stream(message)` | Send a message, stream response tokens |
| `reset()` | Clear conversation history |
| `get_history()` | Return a copy of conversation history |

## Running the Examples

### 1. Create a Moss index (one-time setup)

```bash
export MOSS_PROJECT_ID=your-project-id
export MOSS_PROJECT_KEY=your-project-key
export MOSS_INDEX_NAME=my-faq-index

python examples/moss-create-index-demo.py
```

### 2. Start the chatbot

```bash
python examples/moss-gemma-demo.py
```

Commands: `/reset` (clear history), `/quit` (exit)

## License

This integration is provided under the [BSD 2-Clause License](LICENSE).

## Support

- [Moss Docs](https://docs.usemoss.dev)
- [Moss Discord](https://discord.com/invite/eMXExuafBR)
- [Ollama Docs](https://ollama.com/docs)
```

- [ ] **Step 2: Commit**

```bash
cd ../..
git add packages/gemma-moss/README.md
git commit -m "docs: add full README for gemma-moss"
```

---

### Task 8: Final verification

**Files:** (no new files)

- [ ] **Step 1: Run full test suite**

```bash
cd packages/gemma-moss && uv run pytest tests/ -v --tb=short
```

Expected: all 28 tests PASS.

- [ ] **Step 2: Run linter and formatter**

```bash
cd packages/gemma-moss && uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/
```

Expected: no errors.

- [ ] **Step 3: Verify package structure**

```bash
cd packages/gemma-moss && find . -type f -not -path './.venv/*' -not -path './__pycache__/*' -not -name '*.pyc' -not -name 'uv.lock' | sort
```

Expected output should include all files from the file map.

- [ ] **Step 4: Verify imports work**

```bash
cd packages/gemma-moss && uv run python -c "from gemma_moss import MossRetriever, GemmaMossSession, DefaultContextFormatter, make_ollama_query_rewriter; print('All imports OK')"
```

Expected: `All imports OK`

- [ ] **Step 5: Final commit (if any fixups needed)**

```bash
cd ../..
git add packages/gemma-moss/
git commit -m "chore: final cleanup for gemma-moss package"
```

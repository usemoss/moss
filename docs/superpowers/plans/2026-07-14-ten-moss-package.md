# ten-moss Package (PR 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Revision 2026-07-15:** This plan describes the original `MossRetrievalStore` /
> `MossRetrievalConfig` design. During review it was reframed to a **Moss session
> manager** built on the Moss Sessions API: `MossSessionManager` /
> `MossSessionConfig` with `open()`, `query_context(text)`, `add_docs()`,
> `get_docs()`, `delete_docs()`, `push_index()`, `doc_count`. The delivery also
> collapsed from 3 PRs to 2 (package + full Moss-wired app). See the design spec's
> revision note for the authoritative surface.

**Goal:** Build `packages/ten-moss/`, a reusable Python helper exposing `MossRetrievalStore` (ambient RAG for TEN extensions) and `MossRetrievalConfig`, with offline tests and a create-index helper.

**Architecture:** A thin, TEN-agnostic wrapper over the Moss Python SDK. `MossRetrievalStore` loads an index once, runs a hybrid query per turn, and formats retrieved passages into a context block; failures degrade to `""` so a voice loop never stalls. `MossRetrievalConfig` is a pydantic model that standardizes `moss_*` property names for the TEN app (PR 3) to extend.

**Tech Stack:** Python (src layout), Moss SDK (`moss`), pydantic v2, loguru, uv (env + lockfile), ruff (lint/format), `unittest.IsolatedAsyncioTestCase` (run via pytest).

## Global Constraints

- Python floor: `requires-python = ">=3.10,<3.15"` (Moss SDK requires 3.10+).
- Package name `ten-moss`; import name `ten_moss`; **src layout** under `src/ten_moss/`.
- Runtime deps: `moss>=1.1.1`, `pydantic>=2.0.0`, `loguru>=0.7.0`. Dev deps: `pytest>=8.0`, `ruff>=0.1.0`, `python-dotenv>=1.0` (examples only).
- License: **BSD-2-Clause** — copy the repo root `LICENSE` verbatim.
- Follow `packages/pipecat-moss/` conventions: ruff config, google-convention docstrings, `[dependency-groups] dev`.
- Tests are **offline**: mock `ten_moss.moss_retrieval_store.MossClient` with `unittest.mock` (no network, no creds), matching `examples/cookbook/langchain/test_integration.py`. Run with `uv run pytest tests/ -v` from `packages/ten-moss/`.
- `MossRetrievalStore.retrieve()` MUST NOT raise on query failure/timeout/empty — it returns `""`.
- Commits: **no `Co-Authored-By` trailer.**

## Exact Moss SDK surface (verified from `sdks/python/sdk/src/moss/__init__.pyi`)

- `MossClient(project_id: str, project_key: str)` — positional args.
- `await client.load_index(name: str, auto_refresh=False, polling_interval_in_seconds=600) -> str`
- `await client.query(name: str, query: str, options: QueryOptions | None) -> SearchResult`
- `QueryOptions(embedding=None, top_k=None, alpha=None, filter=None)`
- `SearchResult.docs: list[QueryResultDocumentInfo]`, `.query`, `.index_name`, `.time_taken_ms`
- `QueryResultDocumentInfo`: `.id: str`, `.text: str`, `.metadata: dict|None`, `.score: float`
- `DocumentInfo(id: str, text: str, metadata: dict|None=None, embedding=None)`
- `await client.create_index(name: str, docs: list[DocumentInfo], model_id: str|None) -> MutationResult`

## File Structure

```
packages/ten-moss/
  pyproject.toml                     # Task 1
  LICENSE                            # Task 1 (copy of root LICENSE)
  .gitignore                         # Task 1
  .env.example                       # Task 4
  README.md                          # Task 4
  CHANGELOG.md                       # Task 4
  CONTRIBUTING.md                    # Task 4
  src/ten_moss/
    __init__.py                      # Task 1 (config), extended Task 2 (store + re-exports)
    config.py                        # Task 1  -> MossRetrievalConfig
    moss_retrieval_store.py          # Task 2 (ctor + format_context), Task 3 (load/retrieve/from_config)
  examples/
    create_index.py                  # Task 4  -> build_documents(), main()
  tests/
    test_retrieval_store.py          # Tasks 1-4 (grows per task)
```

Repo docs touched (Task 4): `AGENTS.md` (packages list), root `README.md` (integrations).

---

### Task 1: Scaffold package + `MossRetrievalConfig`

**Files:**
- Create: `packages/ten-moss/pyproject.toml`
- Create: `packages/ten-moss/LICENSE`
- Create: `packages/ten-moss/.gitignore`
- Create: `packages/ten-moss/src/ten_moss/config.py`
- Create: `packages/ten-moss/src/ten_moss/__init__.py`
- Test: `packages/ten-moss/tests/test_retrieval_store.py`

**Interfaces:**
- Produces: `ten_moss.MossRetrievalConfig` — pydantic `BaseModel` with fields `moss_project_id: str = ""`, `moss_project_key: str = ""`, `moss_index_name: str = ""`, `moss_top_k: int = 5`, `moss_alpha: float = 0.8`, `moss_context_header: str = "Relevant knowledge from Moss:"`, `enable_moss: bool = True`.

- [ ] **Step 1: Write the failing test**

Create `packages/ten-moss/tests/test_retrieval_store.py`:

```python
"""Offline tests for the ten-moss helper package."""

import unittest

from ten_moss import MossRetrievalConfig


class TestMossRetrievalConfig(unittest.TestCase):
    """MossRetrievalConfig defaults and overrides."""

    def test_defaults(self):
        cfg = MossRetrievalConfig()
        self.assertEqual(cfg.moss_project_id, "")
        self.assertEqual(cfg.moss_project_key, "")
        self.assertEqual(cfg.moss_index_name, "")
        self.assertEqual(cfg.moss_top_k, 5)
        self.assertEqual(cfg.moss_alpha, 0.8)
        self.assertEqual(cfg.moss_context_header, "Relevant knowledge from Moss:")
        self.assertTrue(cfg.enable_moss)

    def test_overrides(self):
        cfg = MossRetrievalConfig(
            moss_project_id="p", moss_index_name="idx", moss_top_k=3, enable_moss=False
        )
        self.assertEqual(cfg.moss_project_id, "p")
        self.assertEqual(cfg.moss_index_name, "idx")
        self.assertEqual(cfg.moss_top_k, 3)
        self.assertFalse(cfg.enable_moss)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Create scaffolding so the test can import the package**

Create `packages/ten-moss/pyproject.toml`:

```toml
[project]
name = "ten-moss"
version = "0.0.1"
description = "Moss ambient semantic retrieval for the TEN Framework"
readme = "README.md"
requires-python = ">=3.10,<3.15"
license = { text = "BSD-2-Clause" }
authors = [{ name = "InferEdge Inc.", email = "contact@moss.dev" }]
dependencies = [
    "moss>=1.1.1",
    "pydantic>=2.0.0",
    "loguru>=0.7.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "ruff>=0.1.0",
    "python-dotenv>=1.0",
]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "UP", "D"]
ignore = ["D100", "D104"]

[tool.ruff.lint.per-file-ignores]
"examples/*.py" = ["E501"]
"tests/*.py" = ["D"]

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
```

Create `packages/ten-moss/.gitignore`:

```gitignore
__pycache__/
*.py[cod]
.venv/
.env
*.egg-info/
dist/
build/
.pytest_cache/
.ruff_cache/
```

Create `packages/ten-moss/LICENSE` by copying the repo root license:

Run: `cp LICENSE packages/ten-moss/LICENSE` (from repo root).

Create `packages/ten-moss/src/ten_moss/config.py`:

```python
"""Configuration model for Moss ambient retrieval in TEN extensions."""

from __future__ import annotations

from pydantic import BaseModel


class MossRetrievalConfig(BaseModel):
    """Standardized `moss_*` properties consumed from a TEN `property.json`.

    A TEN extension's own config model can inherit these fields so property
    names stay consistent across integrations.
    """

    moss_project_id: str = ""
    moss_project_key: str = ""
    moss_index_name: str = ""
    moss_top_k: int = 5
    moss_alpha: float = 0.8
    moss_context_header: str = "Relevant knowledge from Moss:"
    enable_moss: bool = True
```

Create `packages/ten-moss/src/ten_moss/__init__.py`:

```python
"""Moss ambient semantic retrieval for the TEN Framework."""

from __future__ import annotations

from .config import MossRetrievalConfig

__all__ = ["MossRetrievalConfig"]
```

- [ ] **Step 3: Run test to verify it fails, then passes after install**

Run (from `packages/ten-moss/`): `uv sync && uv run pytest tests/ -v`
Expected: `TestMossRetrievalConfig::test_defaults PASSED`, `test_overrides PASSED` (2 passed).

Note: `uv sync` creates the venv and installs `moss`, `pydantic`, `loguru`, and dev tools. If `moss` has no wheel for the interpreter uv selects, pin one it does: `uv python pin 3.12 && uv sync`.

- [ ] **Step 4: Lint**

Run (from `packages/ten-moss/`): `uv run ruff check . && uv run ruff format --check .`
Expected: `All checks passed!` (format may report files would be reformatted — if so run `uv run ruff format .` then re-check).

- [ ] **Step 5: Commit**

```bash
git add packages/ten-moss/pyproject.toml packages/ten-moss/LICENSE packages/ten-moss/.gitignore \
  packages/ten-moss/src/ten_moss/__init__.py packages/ten-moss/src/ten_moss/config.py \
  packages/ten-moss/tests/test_retrieval_store.py packages/ten-moss/uv.lock
git commit -m "feat(ten-moss): scaffold package and MossRetrievalConfig"
```

---

### Task 2: `MossRetrievalStore` constructor + `format_context`

**Files:**
- Create: `packages/ten-moss/src/ten_moss/moss_retrieval_store.py`
- Modify: `packages/ten-moss/src/ten_moss/__init__.py`
- Test: `packages/ten-moss/tests/test_retrieval_store.py`

**Interfaces:**
- Consumes: `ten_moss.MossRetrievalConfig` (Task 1).
- Produces:
  - `MossRetrievalStore(*, project_id: str, project_key: str, index_name: str, top_k: int = 5, alpha: float = 0.8, context_header: str = "Relevant knowledge from Moss:", timeout_s: float = 2.0, logger=None)`.
  - `MossRetrievalStore.format_context(docs) -> str` — returns `"{header}\n\n[1] {text}\n[2] {text}"`; header only if `docs` empty.

- [ ] **Step 1: Write the failing test**

Append to `packages/ten-moss/tests/test_retrieval_store.py` (add import at top: `from unittest.mock import patch` and `from ten_moss import MossRetrievalStore`):

```python
class _Doc:
    """Minimal stand-in for a Moss QueryResultDocumentInfo."""

    def __init__(self, text, score=0.0, id="d", metadata=None):
        self.text = text
        self.score = score
        self.id = id
        self.metadata = metadata or {}


class TestFormatContext(unittest.TestCase):
    """MossRetrievalStore.format_context formatting."""

    def _store(self, **kw):
        with patch("ten_moss.moss_retrieval_store.MossClient"):
            return MossRetrievalStore(
                project_id="p", project_key="k", index_name="idx", **kw
            )

    def test_formats_numbered_passages_under_header(self):
        store = self._store(context_header="Knowledge:")
        out = store.format_context([_Doc("alpha"), _Doc("beta")])
        self.assertIn("Knowledge:", out)
        self.assertIn("[1] alpha", out)
        self.assertIn("[2] beta", out)

    def test_strips_whitespace_in_passages(self):
        store = self._store()
        out = store.format_context([_Doc("  spaced  ")])
        self.assertIn("[1] spaced", out)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_retrieval_store.py::TestFormatContext -v`
Expected: FAIL with `ImportError: cannot import name 'MossRetrievalStore'`.

- [ ] **Step 3: Write minimal implementation**

Create `packages/ten-moss/src/ten_moss/moss_retrieval_store.py`:

```python
"""Ambient Moss retrieval store for TEN extensions."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from moss import MossClient

__all__ = ["MossRetrievalStore"]


def _default_logger() -> Any:
    from loguru import logger

    return logger


class MossRetrievalStore:
    """Loads a Moss index and returns formatted context for a user query.

    Retrieval never raises into the caller: on timeout, error, or no hits it
    returns an empty string so the voice loop keeps flowing.
    """

    def __init__(
        self,
        *,
        project_id: str,
        project_key: str,
        index_name: str,
        top_k: int = 5,
        alpha: float = 0.8,
        context_header: str = "Relevant knowledge from Moss:",
        timeout_s: float = 2.0,
        logger: Any = None,
    ) -> None:
        """Store client and per-query retrieval settings."""
        self._client = MossClient(project_id, project_key)
        self._index_name = index_name
        self._top_k = top_k
        self._alpha = alpha
        self._context_header = context_header
        self._timeout_s = timeout_s
        self._log = logger or _default_logger()
        self._loaded = False

    def format_context(self, docs: Sequence[Any]) -> str:
        """Format retrieved passages into a single context block."""
        if not docs:
            return self._context_header.rstrip()
        lines = [self._context_header.rstrip(), ""]
        for idx, doc in enumerate(docs, start=1):
            text = (getattr(doc, "text", "") or "").strip()
            lines.append(f"[{idx}] {text}")
        return "\n".join(lines).strip()
```

Replace `packages/ten-moss/src/ten_moss/__init__.py` with:

```python
"""Moss ambient semantic retrieval for the TEN Framework."""

from __future__ import annotations

from moss import DocumentInfo, MossClient, QueryOptions, SearchResult

from .config import MossRetrievalConfig
from .moss_retrieval_store import MossRetrievalStore

__all__ = [
    "DocumentInfo",
    "MossClient",
    "MossRetrievalConfig",
    "MossRetrievalStore",
    "QueryOptions",
    "SearchResult",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_retrieval_store.py::TestFormatContext -v`
Expected: 2 passed.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check . && uv run ruff format .
git add src/ten_moss/moss_retrieval_store.py src/ten_moss/__init__.py tests/test_retrieval_store.py
git commit -m "feat(ten-moss): add MossRetrievalStore with format_context"
```

---

### Task 3: `load()`, `retrieve()`, and `from_config()`

**Files:**
- Modify: `packages/ten-moss/src/ten_moss/moss_retrieval_store.py`
- Test: `packages/ten-moss/tests/test_retrieval_store.py`

**Interfaces:**
- Consumes: `MossClient.load_index`, `MossClient.query`, `QueryOptions` (from `moss`); `MossRetrievalConfig` (Task 1).
- Produces:
  - `async MossRetrievalStore.load() -> None` — calls `client.load_index(index_name)`; raises on failure.
  - `async MossRetrievalStore.retrieve(query: str) -> str` — hybrid query, returns `format_context(docs)` or `""` (blank query / no hits / exception / timeout).
  - `classmethod MossRetrievalStore.from_config(config: MossRetrievalConfig, *, logger=None) -> MossRetrievalStore`.

- [ ] **Step 1: Write the failing tests**

Append to `packages/ten-moss/tests/test_retrieval_store.py` (add imports at top: `import asyncio` and `from unittest.mock import AsyncMock, MagicMock`; `from ten_moss import MossRetrievalConfig` is already imported):

```python
class TestRetrieve(unittest.IsolatedAsyncioTestCase):
    """MossRetrievalStore.load / retrieve behavior with a mocked MossClient."""

    def _store_with_mock(self, mock_client_cls, **kw):
        mock_client = mock_client_cls.return_value
        mock_client.load_index = AsyncMock(return_value="ok")
        mock_client.query = AsyncMock(return_value=MagicMock(docs=[]))
        store = MossRetrievalStore(
            project_id="p", project_key="k", index_name="idx", **kw
        )
        return store, mock_client

    @patch("ten_moss.moss_retrieval_store.MossClient")
    async def test_load_calls_load_index_once(self, cls):
        store, client = self._store_with_mock(cls)
        await store.load()
        client.load_index.assert_awaited_once_with("idx")

    @patch("ten_moss.moss_retrieval_store.MossClient")
    async def test_retrieve_maps_results_to_context(self, cls):
        store, client = self._store_with_mock(cls)
        client.query = AsyncMock(
            return_value=MagicMock(docs=[_Doc("first"), _Doc("second")])
        )
        out = await store.retrieve("q")
        self.assertIn("[1] first", out)
        self.assertIn("[2] second", out)

    @patch("ten_moss.moss_retrieval_store.MossClient")
    async def test_retrieve_empty_results_returns_blank(self, cls):
        store, client = self._store_with_mock(cls)
        self.assertEqual(await store.retrieve("q"), "")

    @patch("ten_moss.moss_retrieval_store.MossClient")
    async def test_retrieve_blank_query_skips_client(self, cls):
        store, client = self._store_with_mock(cls)
        self.assertEqual(await store.retrieve("   "), "")
        client.query.assert_not_awaited()

    @patch("ten_moss.moss_retrieval_store.MossClient")
    async def test_retrieve_swallows_exception(self, cls):
        store, client = self._store_with_mock(cls)
        client.query = AsyncMock(side_effect=RuntimeError("boom"))
        self.assertEqual(await store.retrieve("q"), "")

    @patch("ten_moss.moss_retrieval_store.MossClient")
    async def test_retrieve_times_out_to_blank(self, cls):
        store, client = self._store_with_mock(cls, timeout_s=0.01)

        async def _slow(*a, **k):
            await asyncio.sleep(0.1)
            return MagicMock(docs=[_Doc("late")])

        client.query = AsyncMock(side_effect=_slow)
        self.assertEqual(await store.retrieve("q"), "")

    @patch("ten_moss.moss_retrieval_store.MossClient")
    async def test_from_config_builds_store(self, cls):
        cfg = MossRetrievalConfig(
            moss_project_id="p", moss_project_key="k", moss_index_name="idx",
            moss_top_k=7, moss_alpha=0.5, moss_context_header="H",
        )
        store = MossRetrievalStore.from_config(cfg)
        self.assertEqual(store._index_name, "idx")
        self.assertEqual(store._top_k, 7)
        self.assertEqual(store._alpha, 0.5)
        self.assertEqual(store._context_header, "H")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_retrieval_store.py::TestRetrieve -v`
Expected: FAIL with `AttributeError: 'MossRetrievalStore' object has no attribute 'load'` (and similar).

- [ ] **Step 3: Write minimal implementation**

In `packages/ten-moss/src/ten_moss/moss_retrieval_store.py`, add `import asyncio` and `from moss import QueryOptions` at the top, add `from .config import MossRetrievalConfig` (under `TYPE_CHECKING` is unnecessary — no cycle), and add these methods to the class (after `format_context`):

```python
    async def load(self) -> None:
        """Load the configured index once at startup. Raises on failure."""
        await self._client.load_index(self._index_name)
        self._loaded = True

    async def retrieve(self, query: str) -> str:
        """Return a context block for `query`, or '' on blank/no-hit/error."""
        text = (query or "").strip()
        if not text:
            return ""
        try:
            result = await asyncio.wait_for(
                self._client.query(
                    self._index_name,
                    text,
                    options=QueryOptions(top_k=self._top_k, alpha=self._alpha),
                ),
                timeout=self._timeout_s,
            )
        except Exception as exc:  # noqa: BLE001 - never break the voice loop
            self._log.error(f"[ten-moss] retrieval failed for query={text!r}: {exc}")
            return ""
        docs = getattr(result, "docs", None) or []
        if not docs:
            return ""
        return self.format_context(docs)

    @classmethod
    def from_config(
        cls, config: MossRetrievalConfig, *, logger: Any = None
    ) -> MossRetrievalStore:
        """Build a store from a MossRetrievalConfig."""
        return cls(
            project_id=config.moss_project_id,
            project_key=config.moss_project_key,
            index_name=config.moss_index_name,
            top_k=config.moss_top_k,
            alpha=config.moss_alpha,
            context_header=config.moss_context_header,
            logger=logger,
        )
```

- [ ] **Step 4: Run the full test file to verify it passes**

Run: `uv run pytest tests/ -v`
Expected: all tests pass (config + format_context + retrieve = 11 passed).

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check . && uv run ruff format .
git add src/ten_moss/moss_retrieval_store.py tests/test_retrieval_store.py
git commit -m "feat(ten-moss): add async load, retrieve, and from_config"
```

---

### Task 4: create-index helper, docs, and repo integration entries

**Files:**
- Create: `packages/ten-moss/examples/create_index.py`
- Create: `packages/ten-moss/.env.example`
- Create: `packages/ten-moss/README.md`
- Create: `packages/ten-moss/CHANGELOG.md`
- Create: `packages/ten-moss/CONTRIBUTING.md`
- Modify: `AGENTS.md` (packages list)
- Modify: `README.md` (root, integrations mention — optional table row)
- Test: `packages/ten-moss/tests/test_retrieval_store.py`

**Interfaces:**
- Consumes: `moss.DocumentInfo`, `moss.MossClient` (from `moss`).
- Produces: `examples/create_index.py:build_documents() -> list[DocumentInfo]` (10 docs) and `main()` (async) that creates the index.

- [ ] **Step 1: Write the failing test**

Append to `packages/ten-moss/tests/test_retrieval_store.py` (add `import importlib.util` and `import pathlib` at top):

```python
class TestCreateIndexExample(unittest.TestCase):
    """The example script exposes a testable build_documents()."""

    def _load_example(self):
        path = pathlib.Path(__file__).parent.parent / "examples" / "create_index.py"
        spec = importlib.util.spec_from_file_location("_ten_moss_create_index", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_build_documents_returns_ten_docs(self):
        module = self._load_example()
        docs = module.build_documents()
        self.assertEqual(len(docs), 10)
        self.assertTrue(all(d.text for d in docs))
        self.assertEqual(len({d.id for d in docs}), 10)  # unique ids
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_retrieval_store.py::TestCreateIndexExample -v`
Expected: FAIL with `FileNotFoundError` / spec load error (example does not exist yet).

- [ ] **Step 3: Create the example, env, and docs**

Create `packages/ten-moss/examples/create_index.py`:

```python
"""Create and populate a demo Moss index for the ten-moss integration.

Usage:
    export MOSS_PROJECT_ID=... MOSS_PROJECT_KEY=... MOSS_INDEX_NAME=...
    python examples/create_index.py
"""

import asyncio
import os

from dotenv import load_dotenv
from loguru import logger
from moss import DocumentInfo, MossClient


def build_documents() -> list[DocumentInfo]:
    """Return a small support knowledge base for the demo index."""
    return [
        DocumentInfo(id="doc-1", text="Refunds are processed within 3-5 business days once approved.", metadata={"category": "billing"}),
        DocumentInfo(id="doc-2", text="You can track your order from the dashboard under Order History.", metadata={"category": "orders"}),
        DocumentInfo(id="doc-3", text="We offer 24/7 live chat support from the Help menu.", metadata={"category": "support"}),
        DocumentInfo(id="doc-4", text="Standard shipping takes 3-5 business days; express takes 1-2.", metadata={"category": "shipping"}),
        DocumentInfo(id="doc-5", text="Reset your password using the Forgot Password link on the login page.", metadata={"category": "account"}),
        DocumentInfo(id="doc-6", text="We accept Visa, Mastercard, American Express, PayPal, and Apple Pay.", metadata={"category": "billing"}),
        DocumentInfo(id="doc-7", text="Orders can be cancelled within 1 hour of placement.", metadata={"category": "orders"}),
        DocumentInfo(id="doc-8", text="International shipping is available to most countries; rates vary.", metadata={"category": "shipping"}),
        DocumentInfo(id="doc-9", text="Gift wrapping is available at checkout for a small fee.", metadata={"category": "services"}),
        DocumentInfo(id="doc-10", text="We price-match authorized retailers within 14 days of purchase.", metadata={"category": "billing"}),
    ]


async def main() -> None:
    """Create the index named by MOSS_INDEX_NAME from build_documents()."""
    load_dotenv()
    client = MossClient(os.environ["MOSS_PROJECT_ID"], os.environ["MOSS_PROJECT_KEY"])
    index_name = os.environ["MOSS_INDEX_NAME"]
    logger.info("Creating index {}", index_name)
    await client.create_index(name=index_name, docs=build_documents(), model_id="moss-minilm")
    logger.success("Index {} created", index_name)


if __name__ == "__main__":
    asyncio.run(main())
```

Create `packages/ten-moss/.env.example`:

```env
MOSS_PROJECT_ID=your_moss_project_id
MOSS_PROJECT_KEY=your_moss_project_key
MOSS_INDEX_NAME=ten-moss-demo
```

Create `packages/ten-moss/README.md`:

````markdown
# ten-moss

Ambient sub-10ms semantic retrieval for the [TEN Framework](https://github.com/ten-framework/ten-framework), powered by [Moss](https://moss.dev).

`MossRetrievalStore` loads a Moss index once and returns a formatted context
block for each user turn — drop it into a TEN control extension to ground your
voice agent's answers. Retrieval failures degrade to an empty string, so the
voice loop never stalls.

See `apps/ten-moss/` for a full runnable TEN voice-assistant example.

## Install

```bash
pip install ten-moss   # or: uv add ten-moss
```

## Usage

```python
from ten_moss import MossRetrievalStore

store = MossRetrievalStore(
    project_id="...", project_key="...", index_name="support-docs",
    top_k=5, alpha=0.8,
)
await store.load()                      # once, at startup
context = await store.retrieve(user_text)  # per turn; "" on no hits/error
```

Or build it from TEN properties:

```python
from ten_moss import MossRetrievalConfig, MossRetrievalStore

config = MossRetrievalConfig(**props)          # moss_* fields from property.json
store = MossRetrievalStore.from_config(config)
```

## Configuration (`MossRetrievalConfig`)

| Field | Default | Meaning |
| --- | --- | --- |
| `moss_project_id` | `""` | Moss project id |
| `moss_project_key` | `""` | Moss project key |
| `moss_index_name` | `""` | index to load and query |
| `moss_top_k` | `5` | results per query |
| `moss_alpha` | `0.8` | semantic/keyword blend (1.0 semantic, 0.0 keyword) |
| `moss_context_header` | `"Relevant knowledge from Moss:"` | header of the injected block |
| `enable_moss` | `true` | master toggle |

## Create a demo index

```bash
cp .env.example .env   # fill in your Moss credentials
python examples/create_index.py
```

## Development

```bash
uv sync
uv run pytest tests/ -v
uv run ruff check .
```

## License

BSD-2-Clause.
````

Create `packages/ten-moss/CHANGELOG.md`:

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.1] - 2026-07-14

### Added
- `MossRetrievalStore` — ambient Moss retrieval with `load`, `retrieve`, `format_context`, and `from_config`.
- `MossRetrievalConfig` — standardized `moss_*` properties for TEN extensions.
- `examples/create_index.py` — create and populate a demo index.
```

Create `packages/ten-moss/CONTRIBUTING.md`:

```markdown
# Contributing to ten-moss

## Setup

```bash
cd packages/ten-moss
uv sync
```

## Test & lint

```bash
uv run pytest tests/ -v
uv run ruff check .
uv run ruff format --check .
```

Tests are offline (the Moss client is mocked) — no credentials required.
```

- [ ] **Step 4: Add the package to repo docs**

In `AGENTS.md`, under the `packages/` section list (Repository Layout), add a line after the `strands-agents-moss/` entry:

```
  ten-moss/              — TEN Framework ambient Moss retrieval helper (MossRetrievalStore)
```

In root `README.md`, if there is an integrations list/table, add a `ten-moss` / TEN Framework entry consistent with the surrounding format. (If no such list exists, skip this edit — do not invent a new section.)

- [ ] **Step 5: Run all tests + lint to verify**

Run: `uv run pytest tests/ -v && uv run ruff check . && uv run ruff format --check .`
Expected: all tests pass (12 total), ruff clean.

- [ ] **Step 6: Commit**

```bash
git add packages/ten-moss/examples/create_index.py packages/ten-moss/.env.example \
  packages/ten-moss/README.md packages/ten-moss/CHANGELOG.md packages/ten-moss/CONTRIBUTING.md \
  packages/ten-moss/tests/test_retrieval_store.py AGENTS.md README.md
git commit -m "docs(ten-moss): add create-index example, docs, and repo integration entry"
```

---

## Self-Review

**Spec coverage:**
- `MossRetrievalStore` (load/retrieve/format_context) → Tasks 2-3. ✓
- `MossRetrievalConfig` standardized `moss_*` fields → Task 1. ✓
- `from_config` convenience for PR 3 → Task 3. ✓
- Timeout guard + never-raise retrieval → Task 3 (`test_retrieve_times_out_to_blank`, `test_retrieve_swallows_exception`). ✓
- `examples/create_index.py` → Task 4. ✓
- Offline CI-able tests → all tasks (mocked). Note: this refines the spec's "ephemeral live index" idea to the repo's mocked-client convention — same intent (CI-green without external calls), more robust. ✓
- Packaging + docs (README/CHANGELOG/CONTRIBUTING/.env.example/LICENSE) → Tasks 1 & 4. ✓
- AGENTS.md package entry → Task 4. ✓

**Placeholder scan:** No TBD/TODO; every code step has full code; every run step has a command + expected output. ✓

**Type consistency:** `MossRetrievalStore` ctor is keyword-only across Tasks 2-3; `format_context(docs)`, `load()`, `retrieve(query)`, `from_config(config)` names/signatures match between the Interfaces blocks, implementation, and tests. `MossRetrievalConfig` field names (`moss_*`) are identical in Task 1, `from_config` (Task 3), and README (Task 4). Query call uses `options=QueryOptions(top_k=, alpha=)` matching the verified SDK stub. ✓

Out of scope for PR 1 (per spec): the TEN app, the `main_python` delta, memorization, standalone graph node.
```

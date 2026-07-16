"""Moss-backed archival memory adapter for Letta (MemGPT) agents.

Letta removed its pluggable storage-backend abstraction for archival memory;
today's archival memory is hardcoded to Postgres/pgvector, Turbopuffer, or
Pinecone with no public extension point. This module instead wraps Moss as a
standalone memory store that Letta agents call through tools (see
``letta_moss.tools`` and ``letta_moss.mcp_app``), following the pattern
Letta's own docs recommend for external memory providers.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from typing import Any

from moss import (
    DocumentInfo,
    GetDocumentsOptions,
    MossClient,
    MutationOptions,
    QueryOptions,
)

_MOSS_TYPED_PREFIX = "__moss_typed__:"

# When `tags` is set, oversample the Moss-side query by this factor before
# applying the client-side tag filter, so truncating to `top_k` afterward is
# less likely to silently drop tag-matching memories that ranked just outside
# the raw top_k window. Bounded, not a guarantee: Moss has no native way to
# filter on the tags blob, so a true exhaustive match still isn't possible.
_TAGS_OVERSAMPLE_FACTOR = 4


def _serialize_metadata(meta: dict[str, Any] | None) -> dict[str, str] | None:
    """Convert arbitrary-typed metadata to Moss string-only metadata.

    Moss only accepts string values in metadata. Non-string values are
    JSON-encoded and prefixed with ``__moss_typed__:`` so the deserializer
    can recover the original type. Plain strings are stored as-is, *unless*
    they already start with the ``__moss_typed__:`` sentinel themselves, in
    which case they're JSON-encoded too so the deserializer can't mistake a
    literal string for an encoded value.
    """
    if meta is None:
        return None

    result: dict[str, str] = {}
    for k, v in meta.items():
        if isinstance(v, str) and not v.startswith(_MOSS_TYPED_PREFIX):
            result[k] = v
        else:
            result[k] = f"{_MOSS_TYPED_PREFIX}{json.dumps(v)}"
    return result


def _deserialize_metadata(meta: dict[str, str] | None) -> dict[str, Any]:
    """Convert Moss string metadata back to original types.

    Values prefixed with ``__moss_typed__:`` are JSON-decoded to restore
    their original type. All other values are returned as plain strings.
    """
    if meta is None:
        return {}

    result: dict[str, Any] = {}
    for k, v in meta.items():
        if isinstance(v, str) and v.startswith(_MOSS_TYPED_PREFIX):
            json_str = v[len(_MOSS_TYPED_PREFIX) :]
            try:
                result[k] = json.loads(json_str)
            except (json.JSONDecodeError, TypeError):
                result[k] = v
        else:
            result[k] = v
    return result


@dataclass
class ArchivalMemoryItem:
    """A single archival memory entry.

    ``score`` is only populated on ``search_memory`` results; inserted or
    fetched-by-id items leave it as ``None``.
    """

    id: str
    content: str
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float | None = None


def _doc_to_item(doc: Any, *, score: float | None = None) -> ArchivalMemoryItem:
    """Convert a Moss ``DocumentInfo``/``QueryResultDocumentInfo`` to an ``ArchivalMemoryItem``."""
    full_meta = _deserialize_metadata(getattr(doc, "metadata", None))
    tags = full_meta.pop("tags", [])
    return ArchivalMemoryItem(
        id=doc.id,
        content=doc.text,
        tags=tags if isinstance(tags, list) else [],
        metadata=full_meta,
        score=score if score is not None else getattr(doc, "score", None),
    )


class MossLettaMemory:
    """Moss-backed archival memory store for a single Letta agent's index.

    Unlike ``agora_moss.MossAgoraSearch`` (explicit constructor args only),
    this adapter falls back to ``MOSS_PROJECT_ID``/``MOSS_PROJECT_KEY`` env
    vars when arguments are omitted. That divergence is deliberate: this
    package is meant to run as a Letta custom tool inside Letta's sandboxed
    tool-execution environment, where env vars (passed via
    ``tool_exec_environment_variables``) are the natural way an agent author
    configures credentials without hardcoding them in tool source.
    """

    def __init__(
        self,
        *,
        project_id: str | None = None,
        project_key: str | None = None,
        index_name: str,
        top_k: int = 5,
        alpha: float = 0.8,
    ) -> None:
        """Initialize the adapter with Moss credentials and index-query defaults."""
        project_id = project_id or os.getenv("MOSS_PROJECT_ID")
        project_key = project_key or os.getenv("MOSS_PROJECT_KEY")
        if not project_id or not project_key:
            raise ValueError(
                "Moss credentials required. Pass project_id/project_key or set "
                "MOSS_PROJECT_ID/MOSS_PROJECT_KEY env vars."
            )
        self._client = MossClient(project_id=project_id, project_key=project_key)
        self._index_name = index_name
        self._top_k = top_k
        self._alpha = alpha
        self._index_loaded = False
        self._index_created = False

    async def load_index(self) -> None:
        """Preload the configured index for fast local queries. Idempotent.

        If the index doesn't exist yet (no memory has ever been inserted),
        this is a no-op rather than an error: call it again after the first
        ``insert_memory()``, or rely on ``search_memory()``'s own internal
        retry.
        """
        if self._index_loaded:
            return
        try:
            await self._client.load_index(self._index_name)
        except RuntimeError as e:
            if "not found" not in str(e).lower():
                raise
            return
        self._index_loaded = True

    async def insert_memory(
        self,
        content: str,
        *,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Insert a new archival memory. Returns the generated memory id.

        Creates the backing Moss index on the first insert if it doesn't
        already exist, matching the pattern in
        ``examples/cookbook/haystack/moss_haystack.py``'s ``write_documents``.
        """
        if metadata and "tags" in metadata:
            raise ValueError(
                "metadata must not contain a 'tags' key; pass tags via the tags= "
                "parameter instead."
            )
        memory_id = str(uuid.uuid4())
        full_meta = {**(metadata or {}), "tags": tags or []}
        doc = DocumentInfo(id=memory_id, text=content, metadata=_serialize_metadata(full_meta))

        if not self._index_created:
            try:
                await self._client.create_index(self._index_name, [doc])
                self._index_created = True
                return memory_id
            except RuntimeError as e:
                if "already exists" not in str(e).lower():
                    raise
                self._index_created = True
                # Index already exists — fall through to add_docs below.

        await self._client.add_docs(self._index_name, [doc], options=MutationOptions(upsert=True))
        return memory_id

    async def search_memory(
        self,
        query: str,
        *,
        top_k: int | None = None,
        tags: list[str] | None = None,
    ) -> list[ArchivalMemoryItem]:
        """Semantically search archival memory.

        Lazily loads the index if it isn't loaded yet (retrying is safe and
        cheap once memories exist); returns an empty list if the index still
        doesn't exist (nothing has been inserted).

        ``tags`` is applied as a client-side post-filter (an item is kept if
        it has any of the given tags), not a Moss-side query filter: tags are
        JSON-encoded into a single string blob via the metadata scheme above,
        and Moss's ``QueryOptions.filter`` grammar only supports ``$eq``-style
        matching against scalar string fields, which can't express "contains
        tag X" against that blob. When ``tags`` is set, the underlying Moss
        query oversamples by ``_TAGS_OVERSAMPLE_FACTOR`` before the tag filter
        runs and the result is truncated back to ``top_k``, so a tag-matching
        memory ranked just outside the raw top-k window is less likely to be
        silently dropped — though with no native tag filter, this remains a
        bounded mitigation, not a guarantee of finding every match.
        """
        await self.load_index()
        if not self._index_loaded:
            return []
        resolved_top_k = top_k if top_k is not None else self._top_k
        query_top_k = resolved_top_k * _TAGS_OVERSAMPLE_FACTOR if tags else resolved_top_k
        options = QueryOptions(top_k=query_top_k, alpha=self._alpha)
        result = await self._client.query(self._index_name, query, options=options)
        items = [_doc_to_item(doc, score=doc.score) for doc in result.docs]
        if tags:
            wanted = set(tags)
            items = [item for item in items if wanted.intersection(item.tags)]
        return items[:resolved_top_k]

    async def delete_memory(self, memory_id: str) -> None:
        """Delete an archival memory by id."""
        await self._client.delete_docs(self._index_name, [memory_id])

    async def get_memory(self, memory_id: str) -> ArchivalMemoryItem | None:
        """Fetch a single archival memory by id, or ``None`` if it doesn't exist."""
        docs = await self._client.get_docs(
            self._index_name, GetDocumentsOptions(doc_ids=[memory_id])
        )
        if not docs:
            return None
        return _doc_to_item(docs[0])

    async def list_memories(self, limit: int | None = None) -> list[ArchivalMemoryItem]:
        """List all archival memories in the index, optionally capped at ``limit``."""
        docs = await self._client.get_docs(self._index_name)
        items = [_doc_to_item(doc) for doc in docs]
        return items[:limit] if limit is not None else items

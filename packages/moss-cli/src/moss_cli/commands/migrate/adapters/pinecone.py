"""Pinecone source adapter with lazy import."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from ....errors import CliValidationError
from .base import SourceAdapter, SourceDocument, SourcePreview


def _import_pinecone() -> Any:
    """Lazy-import the pinecone client, raising a helpful error if missing."""
    try:
        import pinecone  # type: ignore[import-untyped]

        return pinecone
    except ImportError:
        raise CliValidationError(
            "Pinecone client is not installed.",
            hint="Install it with: pip install 'moss-cli[pinecone]'",
        )


class PineconeAdapter(SourceAdapter):
    """Read vectors from a Pinecone index."""

    def __init__(
        self,
        index_name: str,
        environment: str,
        api_key: Optional[str] = None,
        api_key_file: Optional[str] = None,
    ) -> None:
        self._index_name = index_name
        self._environment = environment
        self._api_key = self._resolve_api_key(api_key, api_key_file)
        self._pc: Any = None
        self._index: Any = None
        self._id_list: List[str] = []

    def connect(self) -> None:
        pinecone = _import_pinecone()
        self._pc = pinecone.Pinecone(api_key=self._api_key)
        self._index = self._pc.Index(self._index_name)

    def preview(self) -> SourcePreview:
        if self._index is None:
            raise CliValidationError("Not connected. Call connect() first.")
        stats = self._index.describe_index_stats()
        total = stats.get("total_vector_count", 0)
        dimension = stats.get("dimension", None)
        namespaces = list((stats.get("namespaces") or {}).keys())
        return SourcePreview(
            doc_count=total,
            dimensions=dimension,
            metadata_fields=[],
            extra={"namespaces": namespaces, "source": "pinecone"},
        )

    def stream(self, batch_size: int = 1000) -> Iterator[List[SourceDocument]]:
        if self._index is None:
            raise CliValidationError("Not connected. Call connect() first.")
        # Pinecone list + fetch pattern
        for ids_chunk in self._index.list(limit=batch_size):
            if not ids_chunk:
                break
            fetch_resp = self._index.fetch(ids=ids_chunk)
            vectors = fetch_resp.get("vectors", {})
            batch: List[SourceDocument] = []
            for vid, vdata in vectors.items():
                text = ""
                metadata: Optional[Dict[str, str]] = None
                raw_meta = vdata.get("metadata")
                if raw_meta and isinstance(raw_meta, dict):
                    text = raw_meta.pop("text", "")
                    metadata = {k: str(v) for k, v in raw_meta.items()} if raw_meta else None
                batch.append(
                    SourceDocument(
                        id=vid,
                        text=text,
                        metadata=metadata,
                        embedding=vdata.get("values"),
                    )
                )
            if batch:
                yield batch

    def close(self) -> None:
        self._index = None
        self._pc = None

    @staticmethod
    def _resolve_api_key(
        api_key: Optional[str], api_key_file: Optional[str]
    ) -> str:
        if api_key:
            return api_key
        if api_key_file:
            path = Path(api_key_file)
            if not path.exists():
                raise CliValidationError(f"API key file not found: {api_key_file}")
            return path.read_text().strip()
        env_key = os.environ.get("PINECONE_API_KEY")
        if env_key:
            return env_key
        raise CliValidationError(
            "Pinecone API key not provided.",
            hint="Set PINECONE_API_KEY env var or use --source-api-key-file.",
        )

"""JSON / JSONL file source adapter."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from ....errors import CliValidationError
from .base import SourceAdapter, SourceDocument, SourcePreview


class JsonFileAdapter(SourceAdapter):
    """Read documents from a JSON array or JSONL file."""

    def __init__(self, file_path: str) -> None:
        self._path = Path(file_path)
        self._docs: List[Dict[str, Any]] = []

    def connect(self) -> None:
        if not self._path.exists():
            raise CliValidationError(
                f"File not found: {self._path}",
                hint="Check the path and try again.",
            )
        content = self._path.read_text()
        if self._path.suffix.lower() == ".jsonl":
            self._docs = self._parse_jsonl(content)
        else:
            self._docs = self._parse_json(content)

    def preview(self) -> SourcePreview:
        metadata_fields: set[str] = set()
        dimensions: Optional[int] = None
        for d in self._docs:
            meta = d.get("metadata")
            if isinstance(meta, dict):
                metadata_fields.update(meta.keys())
            emb = d.get("embedding")
            if isinstance(emb, list) and len(emb) > 0 and dimensions is None:
                dimensions = len(emb)

        return SourcePreview(
            doc_count=len(self._docs),
            dimensions=dimensions,
            metadata_fields=sorted(metadata_fields),
            extra={"file": str(self._path), "format": self._path.suffix.lstrip(".")},
        )

    def stream(self, batch_size: int = 1000) -> Iterator[List[SourceDocument]]:
        batch: List[SourceDocument] = []
        for i, raw in enumerate(self._docs):
            doc = self._to_source_doc(raw, i)
            batch.append(doc)
            if len(batch) >= batch_size:
                yield batch
                batch = []
        if batch:
            yield batch

    def close(self) -> None:
        self._docs = []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_json(self, content: str) -> List[Dict[str, Any]]:
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise CliValidationError(
                f"Invalid JSON in {self._path}: {e}",
                hint="Ensure the file is valid JSON.",
            )
        if isinstance(data, dict):
            data = data.get("documents", data.get("docs", []))
        if not isinstance(data, list):
            raise CliValidationError(
                f"Expected a JSON array of documents, got {type(data).__name__}",
            )
        return data

    def _parse_jsonl(self, content: str) -> List[Dict[str, Any]]:
        docs: List[Dict[str, Any]] = []
        for line_no, line in enumerate(content.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                raise CliValidationError(
                    f"Invalid JSON on line {line_no} in {self._path}: {e}",
                )
            if not isinstance(obj, dict):
                raise CliValidationError(
                    f"Line {line_no}: expected a JSON object, got {type(obj).__name__}",
                )
            docs.append(obj)
        return docs

    @staticmethod
    def _to_source_doc(raw: Dict[str, Any], index: int) -> SourceDocument:
        text = raw.get("text")
        if text is None:
            raise CliValidationError(
                f"Document at index {index}: missing required 'text' field",
                hint="Every document must have a 'text' field.",
            )
        doc_id = str(raw.get("id", uuid.uuid4()))
        metadata = raw.get("metadata")
        if metadata is not None and not isinstance(metadata, dict):
            raise CliValidationError(
                f"Document at index {index}: 'metadata' must be a dict",
            )
        embedding = raw.get("embedding")
        if embedding is not None and not isinstance(embedding, list):
            raise CliValidationError(
                f"Document at index {index}: 'embedding' must be a list of floats",
            )
        return SourceDocument(
            id=doc_id,
            text=str(text),
            metadata=metadata,
            embedding=embedding,
        )

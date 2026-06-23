"""HuggingFace Datasets connector.

Streams rows from any HuggingFace dataset via the ``datasets`` library and
yields one ``DocumentInfo`` per row.

Two connector classes are provided:

* **HuggingFaceDatasetConnector** — loads any public (or gated) dataset from
  the HuggingFace Hub by repo ID.
* **HuggingFaceLocalDatasetConnector** — loads a dataset from local files
  (arrow, parquet, json, csv, etc.).

Both connectors support two modes:

**1. Automatic mode** (zero boilerplate) — pass column names instead of a mapper:

    source = HuggingFaceDatasetConnector(
        dataset_name="MongoDB/supply_chain_contracts_dataset_small",
        id_column="Contract Number",
        text_columns=["Goods Description", "Origin", "Destination"],
        metadata_columns=["Shipper", "Receiver", "Value"],
    )

* ``id_column``       — column to use as the document ID.  Falls back to a UUID
  if the column is missing or the value is empty.
* ``text_columns``    — list of columns to join into the document text, or the
  sentinel ``"all"`` to use every column.  When omitted, all columns are used.
* ``metadata_columns``— list of columns to include in ``DocumentInfo.metadata``
  (values are coerced to ``str``), or ``"all"``.  When omitted, all columns
  except the ``id_column`` are included.

**2. Custom mapper mode** (full control) — pass a callable:

    source = HuggingFaceDatasetConnector(
        dataset_name="ag_news",
        mapper=lambda row: DocumentInfo(
            id=str(row["label"]),
            text=row["text"],
            metadata={"category": str(row["label"])},
        ),
    )

Exactly one of ``mapper`` or ``id_column`` / ``text_columns`` must be supplied.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from typing import Any

from datasets import load_dataset
from moss import DocumentInfo

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_ALL = "all"  # sentinel for "use every column"


def auto_mapper(
    row: dict[str, Any],
    id_column: str | None,
    text_columns: list[str] | str,
    metadata_columns: list[str] | str,
) -> DocumentInfo:
    """Build a ``DocumentInfo`` from a raw dataset row without a custom mapper.

    Called internally by the connectors when no ``mapper`` is provided.
    Can also be called directly if you want to use the auto-build logic
    inside a partially custom mapper.
    """
    # ── id ──────────────────────────────────────────────────────────────────
    if id_column and id_column in row and row[id_column] not in (None, ""):
        doc_id = str(row[id_column])
    else:
        doc_id = str(uuid.uuid4())

    # ── text ─────────────────────────────────────────────────────────────────
    if text_columns == _ALL:
        cols_for_text = list(row.keys())
    else:
        cols_for_text = list(text_columns)  # type: ignore[arg-type]

    parts = []
    for col in cols_for_text:
        val = row.get(col)
        if val is None or val == "":
            continue
        if isinstance(val, list):
            val = ", ".join(str(v) for v in val)
        parts.append(f"{col}: {val}.")
    text = " ".join(parts)

    # ── metadata ─────────────────────────────────────────────────────────────
    if metadata_columns == _ALL:
        meta_keys = [k for k in row.keys() if k != id_column]
    else:
        meta_keys = [c for c in metadata_columns if c != id_column]  # type: ignore[union-attr]

    metadata: dict[str, str] = {}
    for col in meta_keys:
        val = row.get(col)
        if val is None:
            continue
        if isinstance(val, list):
            metadata[col] = ", ".join(str(v) for v in val)
        else:
            metadata[col] = str(val)

    return DocumentInfo(id=doc_id, text=text, metadata=metadata or None)


def _resolve_mapper(
    mapper: Callable[[dict[str, Any]], DocumentInfo] | None,
    id_column: str | None,
    text_columns: list[str] | str | None,
    metadata_columns: list[str] | str | None,
) -> Callable[[dict[str, Any]], DocumentInfo]:
    """Return a concrete mapper callable from the user's arguments."""
    if mapper is not None:
        return mapper

    # Auto mode — fill in defaults for unset params
    resolved_text = text_columns if text_columns is not None else _ALL
    resolved_meta = metadata_columns if metadata_columns is not None else _ALL

    def _auto(row: dict[str, Any]) -> DocumentInfo:
        return auto_mapper(row, id_column, resolved_text, resolved_meta)

    return _auto


# ---------------------------------------------------------------------------
# Connectors
# ---------------------------------------------------------------------------


class HuggingFaceDatasetConnector:
    """Stream rows from a HuggingFace Hub dataset and yield one ``DocumentInfo`` per row.

    Provide either ``mapper`` (custom mode) or ``id_column`` / ``text_columns``
    (automatic mode).  See module docstring for full details.

    Args:
        dataset_name: Hub repo ID, e.g. ``"ag_news"``, ``"squad"``,
            ``"MongoDB/supply_chain_contracts_dataset_small"``.
        mapper: Optional callable ``(row: dict) -> DocumentInfo``.  When
            provided, ``id_column``, ``text_columns``, and ``metadata_columns``
            are ignored.
        id_column: Column to use as the document ID (automatic mode).
        text_columns: Columns to join as document text, or ``"all"``
            (automatic mode).
        metadata_columns: Columns to store in metadata, or ``"all"``
            (automatic mode).
        split: Dataset split, e.g. ``"train"``, ``"test"``,
            ``"train[:500]"``.  Defaults to ``"train"``.
        name: Dataset config/subset name (e.g. ``"plain_text"`` for
            Wikipedia).
        streaming: Stream rows without downloading the full dataset
            (default ``True``).
        filter_fn: Optional row-level filter ``(row: dict) -> bool``.
        token: HuggingFace API token for gated/private datasets.
        **load_kwargs: Forwarded to ``datasets.load_dataset()``.
    """

    def __init__(
        self,
        dataset_name: str,
        mapper: Callable[[dict[str, Any]], DocumentInfo] | None = None,
        *,
        id_column: str | None = None,
        text_columns: list[str] | str | None = None,
        metadata_columns: list[str] | str | None = None,
        split: str = "train",
        name: str | None = None,
        streaming: bool = True,
        filter_fn: Callable[[dict[str, Any]], bool] | None = None,
        token: str | None = None,
        **load_kwargs: Any,
    ) -> None:
        if mapper is None and id_column is None and text_columns is None:
            # Default: auto-mode with all columns
            pass  # _resolve_mapper will use ALL sentinel
        self._mapper = _resolve_mapper(mapper, id_column, text_columns, metadata_columns)
        self.dataset_name = dataset_name
        self.split = split
        self.name = name
        self.streaming = streaming
        self.filter_fn = filter_fn
        self.token = token
        self.load_kwargs = load_kwargs

    def __iter__(self) -> Iterator[DocumentInfo]:
        kwargs: dict[str, Any] = {"streaming": self.streaming, **self.load_kwargs}
        if self.name is not None:
            kwargs["name"] = self.name
        if self.token is not None:
            kwargs["token"] = self.token

        dataset = load_dataset(self.dataset_name, split=self.split, **kwargs)

        for row in dataset:
            if self.filter_fn is not None and not self.filter_fn(row):
                continue
            yield self._mapper(row)


class HuggingFaceLocalDatasetConnector:
    """Load a dataset from local files and yield one ``DocumentInfo`` per row.

    Supports any format handled by the ``datasets`` library: JSON / JSONL,
    CSV, Parquet, Arrow, text.

    Provide either ``mapper`` (custom mode) or ``id_column`` / ``text_columns``
    (automatic mode).  See module docstring for full details.

    Args:
        data_files: Path(s) to local files — a string, list, or split-keyed
            dict: ``{"train": "train.parquet"}``.
        mapper: Optional custom mapper callable.
        id_column: Column to use as the document ID (automatic mode).
        text_columns: Columns to join as document text, or ``"all"``.
        metadata_columns: Columns to store in metadata, or ``"all"``.
        split: Which split to iterate.  Defaults to ``"train"``.
        format: File format hint for ``load_dataset`` (e.g. ``"json"``,
            ``"csv"``, ``"parquet"``).  Inferred from extension if omitted.
        streaming: Whether to stream instead of loading all into memory.
        filter_fn: Optional row-level filter.
        **load_kwargs: Forwarded to ``datasets.load_dataset()``.
    """

    def __init__(
        self,
        data_files: str | list[str] | dict[str, str | list[str]],
        mapper: Callable[[dict[str, Any]], DocumentInfo] | None = None,
        *,
        id_column: str | None = None,
        text_columns: list[str] | str | None = None,
        metadata_columns: list[str] | str | None = None,
        split: str = "train",
        format: str | None = None,
        streaming: bool = False,
        filter_fn: Callable[[dict[str, Any]], bool] | None = None,
        **load_kwargs: Any,
    ) -> None:
        self._mapper = _resolve_mapper(mapper, id_column, text_columns, metadata_columns)
        self.data_files = data_files
        self.split = split
        self.format = format
        self.streaming = streaming
        self.filter_fn = filter_fn
        self.load_kwargs = load_kwargs

    def __iter__(self) -> Iterator[DocumentInfo]:
        pos_args = (self.format,) if self.format is not None else ()
        dataset = load_dataset(
            *pos_args,
            data_files=self.data_files,
            split=self.split,
            streaming=self.streaming,
            **self.load_kwargs,
        )

        for row in dataset:
            if self.filter_fn is not None and not self.filter_fn(row):
                continue
            yield self._mapper(row)

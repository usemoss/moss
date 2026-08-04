"""The chunk contract: stable IDs, position metadata, and Moss `DocumentInfo`.

Splitters disagree about *how* to cut text, and that is fine — they are meant to
be swappable. What they must not disagree about is what a chunk looks like once
it comes out. Today they do: `moss-pikachu` emits `{path}#chunk-0001` with
path/filename/chunk/extension/modified_at, while `moss-llamaindex` emits
`{filename}-p{page}-c{idx}` with source/page. Both already wrap chunks in
`DocumentInfo`, so the envelope is shared — but they have no metadata key in
common, so nothing downstream can treat their chunks uniformly.

This module pins down the inside of that envelope.

Position is deliberately *not* a fixed field list. Plain text is located by
character offset, paginated documents by page, code by line; character offsets
are meaningless for a PDF and page numbers are meaningless for a source file. So
every chunk carries a locator whose unit is declared rather than assumed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, get_args

from moss import DocumentInfo

#: Unit a chunk's position is measured in.
LocatorType = Literal["char", "line", "page"]

LOCATOR_TYPES: tuple[str, ...] = get_args(LocatorType)

#: Metadata keys the contract owns. `Chunk.extra` may not shadow them.
RESERVED_KEYS = frozenset({"source", "chunk_index", "locator_type", "locator_start", "locator_end"})


def chunk_id(source: str, index: int) -> str:
    """Build a chunk's stable ID.

    Zero-padded so IDs sort lexicographically in the order they were cut, which
    is what pikachu arrived at independently. `source` is whatever identifies the
    original — a file path, a URL, a document name — and must be stable across
    runs: re-chunking an unchanged document has to reproduce the same IDs, or
    every chunk gets re-added instead of replaced.
    """
    if not source:
        raise ValueError("source must be a non-empty string")
    if index < 0:
        raise ValueError(f"index must be >= 0, got {index}")
    return f"{source}#chunk-{index:04d}"


@dataclass(frozen=True)
class Chunk:
    """One cut of a document, before it becomes a `DocumentInfo`.

    Splitters yield these. Positions stay real integers here; the conversion to
    Moss's string-only metadata happens once, in `to_document`.
    """

    text: str
    index: int
    locator_type: LocatorType
    locator_start: int
    locator_end: int
    extra: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError(f"index must be >= 0, got {self.index}")
        if self.locator_type not in LOCATOR_TYPES:
            raise ValueError(
                f"locator_type must be one of {LOCATOR_TYPES}, got {self.locator_type!r}"
            )
        if self.locator_start < 0:
            raise ValueError(f"locator_start must be >= 0, got {self.locator_start}")
        if self.locator_end < self.locator_start:
            raise ValueError(
                f"locator_end ({self.locator_end}) must be >= locator_start ({self.locator_start})"
            )
        clashes = RESERVED_KEYS & self.extra.keys()
        if clashes:
            raise ValueError(f"extra may not override reserved keys: {sorted(clashes)}")

    def to_document(self, source: str) -> DocumentInfo:
        """Render this chunk as a Moss `DocumentInfo`.

        Every metadata value is stringified because Moss types metadata as
        `Dict[str, str]`. An int left in there would fail at the SDK boundary,
        which is a worse place to discover it than here.
        """
        return DocumentInfo(
            id=chunk_id(source, self.index),
            text=self.text,
            metadata={
                "source": source,
                "chunk_index": str(self.index),
                "locator_type": self.locator_type,
                "locator_start": str(self.locator_start),
                "locator_end": str(self.locator_end),
                **self.extra,
            },
        )

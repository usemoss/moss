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

#: Highest index the ID format can hold. Four digits is pikachu's width, kept for
#: parity; past it the padding stops being fixed-width and `chunk-10000` sorts
#: before `chunk-9999`, which is the one promise the format makes.
MAX_CHUNK_INDEX = 9999


def _require_index(index: int) -> None:
    """Reject anything that is not a plain in-range int.

    `bool` is excluded explicitly because it subclasses `int`, so `True` would
    otherwise format as a perfectly valid `chunk-0001`. A float gets caught here
    rather than at the `:04d` format, which fails with `Unknown format code 'd'`
    a long way from whatever set the index.
    """
    if not isinstance(index, int) or isinstance(index, bool):
        raise TypeError(f"index must be an int, got {type(index).__name__}")
    if index < 0:
        raise ValueError(f"index must be >= 0, got {index}")
    if index > MAX_CHUNK_INDEX:
        raise ValueError(
            f"index must be <= {MAX_CHUNK_INDEX}, got {index}: past that the "
            "zero-padding is no longer fixed width and IDs stop sorting in cut order"
        )


def chunk_id(source: str, index: int) -> str:
    """Build a chunk's stable ID.

    Zero-padded so IDs sort lexicographically in the order they were cut, which
    is what pikachu arrived at independently. `source` is whatever identifies the
    original — a file path, a URL, a document name — and must be stable across
    runs: re-chunking an unchanged document has to reproduce the same IDs, or
    every chunk gets re-added instead of replaced.

    Rejects indices above `MAX_CHUNK_INDEX` rather than emitting an ID that
    breaks the sort. A document that cuts into more than 10,000 chunks wants a
    coarser strategy or a per-section `source`, not a silently unsortable ID.
    """
    if not isinstance(source, str):
        raise TypeError(f"source must be a str, got {type(source).__name__}")
    if not source:
        raise ValueError("source must be a non-empty string")
    _require_index(index)
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
    #: Values are stringified at render, so the natural thing to pass — `{"page":
    #: 3}`, `{"words": 12}` — is accepted rather than failing at the SDK boundary.
    #: Keys must already be strings; see `__post_init__` for why they are not
    #: coerced the same way.
    #:
    #: Copied on construction, so a caller's handle cannot reach back in.
    #:
    #: Excluded from equality and hashing: a chunk *is* its text and position,
    #: and metadata about it does not change which cut of the document it is.
    #: That is also what keeps it safe to leave mutable — nothing here can make a
    #: chunk already sitting in a set change what it equals, whether by rebinding
    #: a key or by mutating a list held as a value.
    extra: dict[str, object] = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
        # The same check `chunk_id` runs, so a chunk that could never render a
        # valid ID is rejected where its index was set rather than mid-render.
        _require_index(self.index)
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
        # Values are coerced at render because `{"page": 3}` is the natural thing
        # to pass and `"3"` is unambiguously what was meant. Keys are rejected
        # instead: `str(1)` and `"1"` are the same metadata key, so coercing them
        # would let one entry silently overwrite another, and a non-string key
        # cannot collide with a reserved one and so slips past the check below.
        non_string = sorted(repr(key) for key in self.extra if not isinstance(key, str))
        if non_string:
            raise TypeError(f"extra keys must be str, got {', '.join(non_string)}")
        clashes = RESERVED_KEYS & self.extra.keys()
        if clashes:
            raise ValueError(f"extra may not override reserved keys: {sorted(clashes)}")
        # `frozen=True` freezes the field, not the dict behind it. Copy so the
        # caller's handle cannot add a reserved key after the check has passed.
        # A plain dict rather than a read-only view, because a `MappingProxyType`
        # is not picklable and takes `deepcopy` and `dataclasses.asdict` down
        # with it. Excluding `extra` from equality is what makes the copy enough.
        object.__setattr__(self, "extra", dict(self.extra))

    def to_document(self, source: str) -> DocumentInfo:
        """Render this chunk as a Moss `DocumentInfo`.

        Every metadata value is stringified because Moss types metadata as
        `Dict[str, str]`. An int left in there would fail at the SDK boundary,
        which is a worse place to discover it than here. Keys are already known
        to be strings — the constructor rejects any that are not.

        `extra` is merged *first* so the contract's own keys always win. The
        constructor already rejects a clashing `extra`, so this only matters if
        one was introduced afterwards — but the whole point of the contract is
        that these five keys mean the same thing on every chunk, and a render
        step is the last place that can still guarantee it.
        """
        return DocumentInfo(
            id=chunk_id(source, self.index),
            text=self.text,
            metadata={
                **{key: str(value) for key, value in self.extra.items()},
                "source": source,
                "chunk_index": str(self.index),
                "locator_type": self.locator_type,
                "locator_start": str(self.locator_start),
                "locator_end": str(self.locator_end),
            },
        )

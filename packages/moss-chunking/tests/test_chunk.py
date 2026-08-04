"""Contract tests: IDs, validation, and the `DocumentInfo` rendering."""

from __future__ import annotations

import pytest
from moss_chunking import Chunk, chunk_id


def test_chunk_id_is_zero_padded_so_it_sorts_in_cut_order():
    ids = [chunk_id("notes.md", i) for i in (0, 1, 9, 10, 100)]
    assert ids[0] == "notes.md#chunk-0000"
    assert ids[3] == "notes.md#chunk-0010"
    assert sorted(ids) == ids


def test_chunk_id_rejects_empty_source():
    with pytest.raises(ValueError, match="non-empty"):
        chunk_id("", 0)


def test_chunk_id_rejects_negative_index():
    with pytest.raises(ValueError, match="index"):
        chunk_id("notes.md", -1)


def test_to_document_stringifies_every_metadata_value():
    doc = Chunk("body", 3, "char", 10, 20).to_document("notes.md")
    assert doc.id == "notes.md#chunk-0003"
    assert doc.text == "body"
    assert doc.metadata == {
        "source": "notes.md",
        "chunk_index": "3",
        "locator_type": "char",
        "locator_start": "10",
        "locator_end": "20",
    }
    assert all(isinstance(value, str) for value in doc.metadata.values())


def test_extra_metadata_is_merged_and_stringified():
    chunk = Chunk("body", 0, "page", 4, 4, extra={"page_label": "iv", "words": "12"})
    doc = chunk.to_document("paper.pdf")
    assert doc.metadata["page_label"] == "iv"
    assert doc.metadata["locator_type"] == "page"


def test_extra_may_not_shadow_reserved_keys():
    with pytest.raises(ValueError, match="reserved"):
        Chunk("body", 0, "char", 0, 4, extra={"source": "elsewhere.md"})


def test_unknown_locator_type_is_rejected():
    with pytest.raises(ValueError, match="locator_type"):
        Chunk("body", 0, "byte", 0, 4)  # type: ignore[arg-type]


def test_backwards_locator_is_rejected():
    with pytest.raises(ValueError, match="locator_end"):
        Chunk("body", 0, "char", 20, 10)


def test_locator_may_be_a_single_point():
    """A page-located chunk starts and ends on the same page."""
    chunk = Chunk("body", 0, "page", 4, 4)
    assert chunk.to_document("paper.pdf").metadata["locator_start"] == "4"

"""Splitter tests.

The invariant every strategy must hold is the roundtrip: a chunk's offsets point
into the original text and slice back to exactly its own text. Get that wrong and
the position metadata is decorative — you can address a chunk but not find it.
"""

from __future__ import annotations

import pytest
from moss_chunking import (
    CharSplitter,
    ParagraphSplitter,
    RecursiveSplitter,
    SentenceSplitter,
    chunk_document,
    prepend_source_context,
)

PROSE = (
    "Moss is a semantic search runtime. It runs on device. "
    "Queries return in under ten milliseconds.\n\n"
    "Chunking decides what a query can match. Cut too coarsely and a hit drags "
    "in noise. Cut too finely and the surrounding context is lost.\n\n"
    "So the strategy has to suit the content."
)

ALL_STRATEGIES = [
    CharSplitter(chunk_chars=120, overlap=20),
    SentenceSplitter(max_words=12, overlap_sentences=1),
    ParagraphSplitter(max_chars=120),
    RecursiveSplitter(max_chars=120),
]


def roundtrips(text: str, chunks) -> bool:
    return all(text[c.locator_start : c.locator_end] == c.text for c in chunks)


@pytest.mark.parametrize("strategy", ALL_STRATEGIES, ids=lambda s: type(s).__name__)
def test_offsets_slice_back_to_the_chunk_text(strategy):
    chunks = list(strategy.split(PROSE))
    assert chunks
    assert roundtrips(PROSE, chunks)


@pytest.mark.parametrize("strategy", ALL_STRATEGIES, ids=lambda s: type(s).__name__)
def test_indices_are_sequential_from_zero(strategy):
    chunks = list(strategy.split(PROSE))
    assert [c.index for c in chunks] == list(range(len(chunks)))


@pytest.mark.parametrize("strategy", ALL_STRATEGIES, ids=lambda s: type(s).__name__)
def test_empty_and_blank_input_yields_nothing(strategy):
    assert list(strategy.split("")) == []
    assert list(strategy.split("   \n\n\t  ")) == []


@pytest.mark.parametrize("strategy", ALL_STRATEGIES, ids=lambda s: type(s).__name__)
def test_chunks_are_never_blank(strategy):
    assert all(c.text.strip() for c in strategy.split(PROSE))


@pytest.mark.parametrize("strategy", ALL_STRATEGIES, ids=lambda s: type(s).__name__)
def test_chunks_advance_through_the_document(strategy):
    starts = [c.locator_start for c in strategy.split(PROSE)]
    assert starts == sorted(starts)


# --- CharSplitter ------------------------------------------------------------


def test_char_splitter_respects_its_ceiling():
    chunks = list(CharSplitter(chunk_chars=50, overlap=10).split(PROSE))
    assert all(len(c.text) <= 50 for c in chunks)


def test_char_splitter_overlaps_by_the_requested_amount():
    text = "a" * 250
    chunks = list(CharSplitter(chunk_chars=100, overlap=30).split(text))
    assert chunks[1].locator_start == chunks[0].locator_end - 30


def test_char_splitter_covers_the_whole_document():
    chunks = list(CharSplitter(chunk_chars=40, overlap=5).split(PROSE))
    assert chunks[0].locator_start == 0
    assert chunks[-1].locator_end == len(PROSE)


def test_overlap_at_or_above_chunk_size_is_rejected():
    with pytest.raises(ValueError, match="never advances"):
        CharSplitter(chunk_chars=100, overlap=100)


def test_short_input_is_a_single_chunk():
    chunks = list(CharSplitter().split("one short line"))
    assert len(chunks) == 1
    assert chunks[0].text == "one short line"


# --- SentenceSplitter --------------------------------------------------------


def test_sentence_splitter_does_not_break_mid_sentence():
    chunks = list(SentenceSplitter(max_words=12, overlap_sentences=1).split(PROSE))
    assert all(c.text.rstrip().endswith((".", "!", "?")) for c in chunks)


def test_sentence_longer_than_the_budget_is_still_emitted():
    text = "This one sentence is deliberately longer than the tiny word budget allows."
    chunks = list(SentenceSplitter(max_words=3).split(text))
    assert len(chunks) == 1
    assert chunks[0].text == text


def test_sentence_splitter_handles_closing_quotes():
    text = 'He said "it works." Then he left. She agreed.'
    chunks = list(SentenceSplitter(max_words=4, overlap_sentences=0).split(text))
    assert roundtrips(text, chunks)
    assert chunks[0].text.startswith("He said")


def test_overlap_is_clamped_so_progress_is_guaranteed():
    splitter = SentenceSplitter(max_words=50, overlap_sentences=99)
    assert splitter.overlap_sentences == 1
    assert list(splitter.split(PROSE))


# --- ParagraphSplitter -------------------------------------------------------


def test_oversized_paragraph_is_emitted_rather_than_cut():
    text = "x" * 500
    chunks = list(ParagraphSplitter(max_chars=100).split(text))
    assert len(chunks) == 1
    assert len(chunks[0].text) == 500


def test_paragraphs_are_packed_together_when_they_fit():
    text = "one.\n\ntwo.\n\nthree."
    assert len(list(ParagraphSplitter(max_chars=1000).split(text))) == 1


def test_paragraphs_are_split_apart_when_they_do_not_fit():
    text = "one.\n\ntwo.\n\nthree."
    assert len(list(ParagraphSplitter(max_chars=6).split(text))) == 3


# --- RecursiveSplitter -------------------------------------------------------


def test_recursive_splitter_always_respects_the_ceiling():
    chunks = list(RecursiveSplitter(max_chars=80).split(PROSE))
    assert all(len(c.text) <= 80 for c in chunks)


def test_recursive_splitter_hard_cuts_unseparated_text():
    text = "x" * 300
    chunks = list(RecursiveSplitter(max_chars=100).split(text))
    assert all(len(c.text) <= 100 for c in chunks)
    assert "".join(c.text for c in chunks) == text


def test_recursive_splitter_prefers_paragraph_boundaries():
    text = "alpha beta.\n\ngamma delta."
    chunks = list(RecursiveSplitter(max_chars=12).split(text))
    assert [c.text for c in chunks] == ["alpha beta.", "gamma delta."]


# --- chunk_document + enrich -------------------------------------------------


def test_chunk_document_renders_documents_under_the_contract():
    docs = chunk_document(PROSE, "notes.md", CharSplitter(chunk_chars=100, overlap=10))
    assert docs
    assert docs[0].id == "notes.md#chunk-0000"
    assert docs[0].metadata["source"] == "notes.md"
    assert docs[0].metadata["locator_type"] == "char"


def test_chunk_document_merges_source_level_extra_metadata():
    docs = chunk_document(
        PROSE,
        "notes.md",
        CharSplitter(chunk_chars=100, overlap=10),
        extra={"extension": "md", "modified_at": "2026-07-28T00:00:00Z"},
    )
    assert all(d.metadata["extension"] == "md" for d in docs)
    assert all(d.metadata["source"] == "notes.md" for d in docs)


def test_chunk_document_rejects_extra_that_shadows_the_contract():
    with pytest.raises(ValueError, match="reserved"):
        chunk_document(PROSE, "notes.md", CharSplitter(), extra={"chunk_index": "9"})


def test_prepend_context_changes_text_but_not_addressing():
    doc = chunk_document(PROSE, "notes.md", CharSplitter())[0]
    enriched = prepend_source_context(doc, filename="notes.md", path="/docs/notes.md")
    assert enriched.id == doc.id
    assert enriched.metadata == doc.metadata
    assert enriched.text.startswith("Filename: notes.md\nPath: /docs/notes.md\n\n")
    assert enriched.text.endswith(doc.text)

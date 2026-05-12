"""Tests for MossSimSearch result formatting and guards."""

from dataclasses import dataclass
from typing import Any

import pytest

from sim_moss.search import MossSimSearch, SimSearchResult


@dataclass
class FakeDoc:
    text: str
    score: float | None = None
    metadata: dict[str, Any] | None = None


class TestFormatResults:
    def test_formats_content_and_score(self):
        docs = [FakeDoc(text="hello", score=0.95)]
        result = MossSimSearch._format_results(docs)
        assert result == [{"content": "hello", "score": 0.95}]

    def test_omits_score_when_none(self):
        docs = [FakeDoc(text="hello", score=None)]
        result = MossSimSearch._format_results(docs)
        assert result == [{"content": "hello"}]

    def test_includes_source_from_metadata(self):
        docs = [FakeDoc(text="hello", score=0.9, metadata={"source": "faq.md"})]
        result = MossSimSearch._format_results(docs)
        assert result == [{"content": "hello", "score": 0.9, "source": "faq.md"}]

    def test_omits_source_when_absent(self):
        docs = [FakeDoc(text="hello", score=0.9, metadata={})]
        result = MossSimSearch._format_results(docs)
        assert "source" not in result[0]

    def test_empty_docs(self):
        assert MossSimSearch._format_results([]) == []

    def test_multiple_docs_order_preserved(self):
        docs = [FakeDoc(text="a", score=0.9), FakeDoc(text="b", score=0.8)]
        result = MossSimSearch._format_results(docs)
        assert len(result) == 2
        assert result[0]["content"] == "a"
        assert result[1]["content"] == "b"

    def test_empty_text_becomes_empty_string(self):
        docs = [FakeDoc(text="")]
        result = MossSimSearch._format_results(docs)
        assert result[0]["content"] == ""


class TestSearchGuard:
    def test_raises_if_index_not_loaded(self):
        search = MossSimSearch.__new__(MossSimSearch)
        search._index_loaded = False
        search._index_name = "test-index"
        with pytest.raises(RuntimeError, match="not loaded"):
            import asyncio

            asyncio.run(search.search("query"))

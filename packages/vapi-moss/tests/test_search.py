"""Tests for MossVapiSearch result formatting and guards."""

from dataclasses import dataclass
from typing import Any

import pytest

from vapi_moss.search import MossVapiSearch, VapiSearchResult


@dataclass
class FakeDoc:
    text: str
    score: float | None = None


class TestFormatResults:
    def test_formats_content_and_similarity(self):
        docs = [FakeDoc(text="hello", score=0.95)]
        result = MossVapiSearch._format_results(docs)
        assert result == [{"content": "hello", "similarity": 0.95}]

    def test_omits_similarity_when_no_score(self):
        docs = [FakeDoc(text="hello", score=None)]
        result = MossVapiSearch._format_results(docs)
        assert result == [{"content": "hello"}]

    def test_empty_docs(self):
        assert MossVapiSearch._format_results([]) == []

    def test_multiple_docs(self):
        docs = [FakeDoc(text="a", score=0.9), FakeDoc(text="b", score=0.8)]
        result = MossVapiSearch._format_results(docs)
        assert len(result) == 2
        assert result[0]["content"] == "a"
        assert result[1]["content"] == "b"


class TestSearchGuard:
    def test_raises_if_index_not_loaded(self):
        search = MossVapiSearch.__new__(MossVapiSearch)
        search._index_loaded = False
        search._index_name = "test"
        with pytest.raises(RuntimeError, match="not loaded"):
            import asyncio
            asyncio.run(search.search("query"))

"""Unit tests for MossAgoraSearch."""

from dataclasses import dataclass

import pytest


@dataclass
class FakeDoc:
    text: str
    score: float | None = None


class TestFormatResults:
    def test_formats_text_and_score_as_content_and_similarity(self):
        from agora_moss.search import MossAgoraSearch

        docs = [FakeDoc(text="hello", score=0.95), FakeDoc(text="world", score=0.5)]
        result = MossAgoraSearch._format_results(docs)
        assert result == [
            {"content": "hello", "similarity": 0.95},
            {"content": "world", "similarity": 0.5},
        ]

    def test_handles_empty_list(self):
        from agora_moss.search import MossAgoraSearch

        assert MossAgoraSearch._format_results([]) == []

    def test_preserves_none_score(self):
        from agora_moss.search import MossAgoraSearch

        docs = [FakeDoc(text="scoreless")]
        result = MossAgoraSearch._format_results(docs)
        assert result == [{"content": "scoreless", "similarity": None}]

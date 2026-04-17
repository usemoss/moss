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


class TestConstructor:
    def test_sets_config_fields(self, monkeypatch):
        # Patch MossClient to avoid real network / credential usage
        import agora_moss.search as search_mod

        constructed = {}

        class FakeClient:
            def __init__(self, *, project_id=None, project_key=None):
                constructed["project_id"] = project_id
                constructed["project_key"] = project_key

        monkeypatch.setattr(search_mod, "MossClient", FakeClient)

        from agora_moss.search import MossAgoraSearch

        s = MossAgoraSearch(
            project_id="p",
            project_key="k",
            index_name="idx",
            top_k=7,
            alpha=0.4,
        )
        assert constructed == {"project_id": "p", "project_key": "k"}
        assert s._index_name == "idx"
        assert s._top_k == 7
        assert s._alpha == 0.4
        assert s._index_loaded is False


class TestLoadIndex:
    async def test_delegates_and_marks_loaded(self, monkeypatch):
        import agora_moss.search as search_mod

        load_calls = []

        class FakeClient:
            def __init__(self, *, project_id=None, project_key=None):
                pass

            async def load_index(self, index_name):
                load_calls.append(index_name)

        monkeypatch.setattr(search_mod, "MossClient", FakeClient)

        from agora_moss.search import MossAgoraSearch

        s = MossAgoraSearch(project_id="p", project_key="k", index_name="idx")
        assert s._index_loaded is False
        await s.load_index()
        assert load_calls == ["idx"]
        assert s._index_loaded is True

    async def test_is_idempotent(self, monkeypatch):
        import agora_moss.search as search_mod

        load_calls = []

        class FakeClient:
            def __init__(self, *, project_id=None, project_key=None):
                pass

            async def load_index(self, index_name):
                load_calls.append(index_name)

        monkeypatch.setattr(search_mod, "MossClient", FakeClient)

        from agora_moss.search import MossAgoraSearch

        s = MossAgoraSearch(project_id="p", project_key="k", index_name="idx")
        await s.load_index()
        await s.load_index()
        assert load_calls == ["idx"]


class TestSearchGuard:
    async def test_raises_if_index_not_loaded(self):
        from agora_moss.search import MossAgoraSearch

        s = MossAgoraSearch.__new__(MossAgoraSearch)
        s._index_loaded = False
        s._index_name = "idx"
        with pytest.raises(RuntimeError, match="not loaded"):
            await s.search("q")

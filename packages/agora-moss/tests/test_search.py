"""Unit tests for MossAgoraSearch."""

import os
from dataclasses import dataclass

import pytest
import pytest as _pytest


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


class TestSearch:
    async def test_delegates_to_client_query_and_returns_formatted_result(self, monkeypatch):
        import agora_moss.search as search_mod

        captured = {}

        class FakeQueryResult:
            def __init__(self, docs, time_taken_ms):
                self.docs = docs
                self.time_taken_ms = time_taken_ms

        class FakeClient:
            def __init__(self, *, project_id=None, project_key=None):
                pass

            async def load_index(self, index_name):
                pass

            async def query(self, index_name, query, *, options):
                captured["index_name"] = index_name
                captured["query"] = query
                captured["top_k"] = options.top_k
                captured["alpha"] = options.alpha
                return FakeQueryResult(
                    docs=[FakeDoc(text="hit", score=0.9)],
                    time_taken_ms=12,
                )

        monkeypatch.setattr(search_mod, "MossClient", FakeClient)

        from agora_moss.search import AgoraSearchResult, MossAgoraSearch

        s = MossAgoraSearch(
            project_id="p",
            project_key="k",
            index_name="idx",
            top_k=3,
            alpha=0.5,
        )
        await s.load_index()
        result = await s.search("what is moss")

        assert captured == {
            "index_name": "idx",
            "query": "what is moss",
            "top_k": 3,
            "alpha": 0.5,
        }
        assert isinstance(result, AgoraSearchResult)
        assert result.documents == [{"content": "hit", "similarity": 0.9}]
        assert result.time_taken_ms == 12


class TestCreateMcpApp:
    def test_returns_fastmcp_with_search_knowledge_base_tool(self, monkeypatch):
        import agora_moss.search as search_mod

        class FakeClient:
            def __init__(self, *, project_id=None, project_key=None):
                pass

        monkeypatch.setattr(search_mod, "MossClient", FakeClient)

        from mcp.server.fastmcp import FastMCP

        from agora_moss.search import MossAgoraSearch, create_mcp_app

        s = MossAgoraSearch(project_id="p", project_key="k", index_name="idx")
        app = create_mcp_app(s)
        assert isinstance(app, FastMCP)

        import asyncio

        tools = asyncio.run(app.list_tools())
        names = [t.name for t in tools]
        assert "search_knowledge_base" in names


class TestPublicAPI:
    def test_package_exports_public_names(self):
        import agora_moss

        assert hasattr(agora_moss, "MossAgoraSearch")
        assert hasattr(agora_moss, "create_mcp_app")
        assert hasattr(agora_moss, "AgoraSearchResult")

    def test_all_lists_only_public_names(self):
        import agora_moss

        assert set(agora_moss.__all__) == {
            "AgoraSearchResult",
            "MossAgoraSearch",
            "create_mcp_app",
        }


class TestMcpErrorMapping:
    async def test_search_exception_is_raised_as_runtime_error_through_tool(self, monkeypatch):
        """The tool handler must re-raise Moss exceptions as RuntimeError.

        FastMCP serializes RuntimeError as an MCP tool-error with a readable
        message. Verified by calling the tool implementation directly.
        """
        import agora_moss.search as search_mod

        class FakeClient:
            def __init__(self, *, project_id=None, project_key=None):
                pass

        monkeypatch.setattr(search_mod, "MossClient", FakeClient)

        from agora_moss.search import MossAgoraSearch, create_mcp_app

        s = MossAgoraSearch(project_id="p", project_key="k", index_name="idx")

        async def broken_search(query):
            raise ValueError("moss blew up")

        s.search = broken_search  # type: ignore[method-assign]
        app = create_mcp_app(s)

        tools = await app.list_tools()
        tool = next(t for t in tools if t.name == "search_knowledge_base")
        # FastMCP stores the registered callable; locate it and invoke directly.
        fn = app._tool_manager.get_tool(tool.name).fn  # type: ignore[attr-defined]

        with pytest.raises(RuntimeError, match="Moss search failed"):
            await fn(query="anything")


_HAS_MOSS_CREDS = bool(os.environ.get("MOSS_PROJECT_ID")) and bool(
    os.environ.get("MOSS_PROJECT_KEY")
)
_MOSS_INDEX = os.environ.get("MOSS_INDEX_NAME", "agora-moss-test")


@_pytest.mark.skipif(
    not _HAS_MOSS_CREDS,
    reason="requires MOSS_PROJECT_ID + MOSS_PROJECT_KEY env vars",
)
class TestMcpRoundtrip:
    async def test_end_to_end_tool_call(self, tmp_path):
        """Spin up the FastMCP streamable-HTTP app and call search_knowledge_base.

        Assumes the index named ``MOSS_INDEX_NAME`` already exists and contains
        at least one document. Use ``apps/agora-moss/create_index.py`` to seed.
        """
        import asyncio
        import socket
        from contextlib import asynccontextmanager

        import httpx
        import uvicorn
        from mcp.client.session import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        from agora_moss import MossAgoraSearch, create_mcp_app

        def free_port() -> int:
            with socket.socket() as s:
                s.bind(("127.0.0.1", 0))
                return s.getsockname()[1]

        port = free_port()
        search = MossAgoraSearch(
            project_id=os.environ["MOSS_PROJECT_ID"],
            project_key=os.environ["MOSS_PROJECT_KEY"],
            index_name=_MOSS_INDEX,
        )
        app = create_mcp_app(search)

        config = uvicorn.Config(
            app.streamable_http_app(),
            host="127.0.0.1",
            port=port,
            log_level="warning",
        )
        server = uvicorn.Server(config)

        @asynccontextmanager
        async def running_server():
            task = asyncio.create_task(server.serve())
            # wait for /mcp to be reachable
            for _ in range(50):
                try:
                    async with httpx.AsyncClient() as http:
                        r = await http.get(f"http://127.0.0.1:{port}/mcp", timeout=0.2)
                        if r.status_code < 500:
                            break
                except (httpx.ConnectError, httpx.ReadTimeout):
                    await asyncio.sleep(0.1)
            try:
                yield
            finally:
                server.should_exit = True
                await task

        async with running_server():
            async with streamablehttp_client(f"http://127.0.0.1:{port}/mcp") as (
                read,
                write,
                _,
            ):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools_response = await session.list_tools()
                    tool_names = [t.name for t in tools_response.tools]
                    assert "search_knowledge_base" in tool_names

                    result = await session.call_tool(
                        "search_knowledge_base",
                        arguments={"query": "hello"},
                    )
                    assert result is not None
                    assert not result.isError

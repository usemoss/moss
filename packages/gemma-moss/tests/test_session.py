"""Tests for GemmaMossSession."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gemma_moss.session import GemmaMossSession


def _mock_retriever(context: str | None = "retrieved context") -> MagicMock:
    """Create a mock retriever with an async retrieve method."""
    retriever = MagicMock()
    retriever.retrieve = AsyncMock(return_value=context)
    return retriever


def _mock_chat_response(content: str = "assistant reply") -> MagicMock:
    """Create a mock Ollama chat response."""
    resp = MagicMock()
    resp.message.content = content
    return resp


@patch("gemma_moss.session.AsyncClient")
class TestGemmaMossSession:
    """Tests for GemmaMossSession."""

    @pytest.mark.asyncio
    async def test_ask_returns_response_string(self, MockAsyncClient):
        """ask() returns the assistant response as a plain string."""
        mock_client = MockAsyncClient.return_value
        mock_client.chat = AsyncMock(return_value=_mock_chat_response("hello"))

        session = GemmaMossSession(
            retriever=_mock_retriever(),
            system_prompt="You are helpful.",
        )
        result = await session.ask("hi")

        assert result == "hello"
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_ask_persists_user_and_assistant_to_history(self, MockAsyncClient):
        """ask() appends the user message and assistant reply to history."""
        mock_client = MockAsyncClient.return_value
        mock_client.chat = AsyncMock(return_value=_mock_chat_response("reply"))

        session = GemmaMossSession(
            retriever=_mock_retriever(),
            system_prompt="You are helpful.",
        )
        await session.ask("hello")

        history = session.get_history()
        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "hello"}
        assert history[1] == {"role": "assistant", "content": "reply"}

    @pytest.mark.asyncio
    async def test_retrieved_context_not_persisted_in_history(self, MockAsyncClient):
        """Retrieved context messages must NOT appear in the persisted history."""
        mock_client = MockAsyncClient.return_value
        mock_client.chat = AsyncMock(return_value=_mock_chat_response("reply"))

        session = GemmaMossSession(
            retriever=_mock_retriever("some context"),
            system_prompt="You are helpful.",
        )
        await session.ask("hello")

        history = session.get_history()
        for msg in history:
            assert msg["content"] != "some context"

    @pytest.mark.asyncio
    async def test_ask_works_when_retriever_returns_none(self, MockAsyncClient):
        """ask() succeeds when the retriever returns None (no results)."""
        mock_client = MockAsyncClient.return_value
        mock_client.chat = AsyncMock(return_value=_mock_chat_response("ok"))

        session = GemmaMossSession(
            retriever=_mock_retriever(None),
            system_prompt="You are helpful.",
        )
        result = await session.ask("question")

        assert result == "ok"
        # Verify no context message was included
        call_args = mock_client.chat.call_args
        messages = call_args[1]["messages"] if "messages" in call_args[1] else call_args[0][0]
        # Should have system + user only (no context message)
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_ask_uses_query_rewriter(self, MockAsyncClient):
        """ask() uses the query_rewriter to transform the query for retrieval."""
        mock_client = MockAsyncClient.return_value
        mock_client.chat = AsyncMock(return_value=_mock_chat_response("answer"))

        rewriter = AsyncMock(return_value="rewritten query")
        retriever = _mock_retriever("context from rewritten")

        session = GemmaMossSession(
            retriever=retriever,
            system_prompt="You are helpful.",
            query_rewriter=rewriter,
        )
        await session.ask("original question")

        rewriter.assert_awaited_once()
        call_args = rewriter.call_args
        assert call_args[0][0] == "original question"
        # History is passed by reference; at call time it was empty
        assert call_args[0][1] is not None
        retriever.retrieve.assert_awaited_once_with("rewritten query")

    @pytest.mark.asyncio
    async def test_rewriter_failure_falls_back_to_raw_message(self, MockAsyncClient):
        """When the query rewriter raises, fall back to using the raw message."""
        mock_client = MockAsyncClient.return_value
        mock_client.chat = AsyncMock(return_value=_mock_chat_response("answer"))

        rewriter = AsyncMock(side_effect=RuntimeError("rewriter broke"))
        retriever = _mock_retriever("context")

        session = GemmaMossSession(
            retriever=retriever,
            system_prompt="You are helpful.",
            query_rewriter=rewriter,
        )
        await session.ask("raw question")

        retriever.retrieve.assert_awaited_once_with("raw question")

    @pytest.mark.asyncio
    async def test_rewriter_empty_string_falls_back_to_raw_message(self, MockAsyncClient):
        """When the query rewriter returns empty string, fall back to raw message."""
        mock_client = MockAsyncClient.return_value
        mock_client.chat = AsyncMock(return_value=_mock_chat_response("answer"))

        rewriter = AsyncMock(return_value="")
        retriever = _mock_retriever("context")

        session = GemmaMossSession(
            retriever=retriever,
            system_prompt="You are helpful.",
            query_rewriter=rewriter,
        )
        await session.ask("raw question")

        retriever.retrieve.assert_awaited_once_with("raw question")

    @pytest.mark.asyncio
    async def test_retrieval_failure_continues_without_context(self, MockAsyncClient):
        """When retriever.retrieve() raises, continue without context."""
        mock_client = MockAsyncClient.return_value
        mock_client.chat = AsyncMock(return_value=_mock_chat_response("ok"))

        retriever = _mock_retriever()
        retriever.retrieve = AsyncMock(side_effect=RuntimeError("retrieval failed"))

        session = GemmaMossSession(
            retriever=retriever,
            system_prompt="You are helpful.",
        )
        result = await session.ask("question")

        assert result == "ok"
        # Should have system + user only (no context)
        call_args = mock_client.chat.call_args
        messages = call_args[1]["messages"]
        assert len(messages) == 2

    @pytest.mark.asyncio
    async def test_reset_clears_history(self, MockAsyncClient):
        """reset() clears all conversation history."""
        mock_client = MockAsyncClient.return_value
        mock_client.chat = AsyncMock(return_value=_mock_chat_response("reply"))

        session = GemmaMossSession(
            retriever=_mock_retriever(),
            system_prompt="You are helpful.",
        )
        await session.ask("hello")
        assert len(session.get_history()) == 2

        session.reset()
        assert len(session.get_history()) == 0

    @pytest.mark.asyncio
    async def test_get_history_returns_copy(self, MockAsyncClient):
        """get_history() returns a copy, so mutations don't affect internal state."""
        mock_client = MockAsyncClient.return_value
        mock_client.chat = AsyncMock(return_value=_mock_chat_response("reply"))

        session = GemmaMossSession(
            retriever=_mock_retriever(),
            system_prompt="You are helpful.",
        )
        await session.ask("hello")

        history = session.get_history()
        history.clear()

        assert len(session.get_history()) == 2

    @pytest.mark.asyncio
    async def test_constructor_copies_initial_history(self, MockAsyncClient):
        """Constructor copies initial history (not by reference)."""
        initial = [{"role": "user", "content": "old"}]

        session = GemmaMossSession(
            retriever=_mock_retriever(),
            system_prompt="You are helpful.",
            history=initial,
        )

        initial.append({"role": "assistant", "content": "extra"})

        history = session.get_history()
        assert len(history) == 1
        assert history[0] == {"role": "user", "content": "old"}

    @pytest.mark.asyncio
    async def test_ask_stream_yields_chunks_and_commits_history(self, MockAsyncClient):
        """ask_stream() yields chunks and commits the full response to history."""
        mock_client = MockAsyncClient.return_value

        # Simulate streaming: ollama.chat(stream=True) returns an awaitable
        # that resolves to an async iterator
        chunk1 = MagicMock()
        chunk1.message.content = "Hello "
        chunk2 = MagicMock()
        chunk2.message.content = "world"
        chunk3 = MagicMock()
        chunk3.message.content = ""  # empty chunk should be filtered

        async def _stream():
            for c in [chunk1, chunk2, chunk3]:
                yield c

        mock_client.chat = AsyncMock(return_value=_stream())

        session = GemmaMossSession(
            retriever=_mock_retriever(),
            system_prompt="You are helpful.",
        )

        chunks = []
        async for chunk in session.ask_stream("hi"):
            chunks.append(chunk)

        # Empty chunks should be filtered out
        assert chunks == ["Hello ", "world"]

        # History should contain the accumulated response
        history = session.get_history()
        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "hi"}
        assert history[1] == {"role": "assistant", "content": "Hello world"}

    @pytest.mark.asyncio
    async def test_message_assembly_order(self, MockAsyncClient):
        """Messages are assembled as [system, *history, context, user]."""
        mock_client = MockAsyncClient.return_value
        mock_client.chat = AsyncMock(return_value=_mock_chat_response("reply"))

        initial_history = [
            {"role": "user", "content": "prev question"},
            {"role": "assistant", "content": "prev answer"},
        ]

        session = GemmaMossSession(
            retriever=_mock_retriever("ctx"),
            system_prompt="Be helpful.",
            history=initial_history,
        )
        await session.ask("new question")

        call_args = mock_client.chat.call_args
        messages = call_args[1]["messages"]

        assert len(messages) == 5
        assert messages[0] == {"role": "system", "content": "Be helpful."}
        assert messages[1] == {"role": "user", "content": "prev question"}
        assert messages[2] == {"role": "assistant", "content": "prev answer"}
        assert messages[3] == {"role": "system", "content": "ctx"}
        assert messages[4] == {"role": "user", "content": "new question"}

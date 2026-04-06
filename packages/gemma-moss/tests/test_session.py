"""Tests for GemmaMossSession."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gemma_moss.session import GemmaMossSession


def _mock_retriever(context: str | None = "retrieved context") -> MagicMock:
    """Create a mock retriever."""
    retriever = MagicMock()
    retriever.retrieve = AsyncMock(return_value=context)
    return retriever


def _mock_response(content: str = "reply", tool_calls=None) -> MagicMock:
    """Create a mock Ollama chat response."""
    resp = MagicMock()
    resp.message.content = content
    resp.message.tool_calls = tool_calls
    return resp


def _mock_tool_call(query: str = "search query") -> MagicMock:
    """Create a mock tool call."""
    tc = MagicMock()
    tc.function.name = "search_knowledge_base"
    tc.function.arguments = {"query": query}
    return tc


@patch("gemma_moss.session.AsyncClient")
class TestGemmaMossSession:
    """Tests for GemmaMossSession."""

    @pytest.mark.asyncio
    async def test_ask_returns_response_no_tool_call(self, MockClient):
        """Direct response when Gemma doesn't call the tool."""
        mock = MockClient.return_value
        mock.chat = AsyncMock(return_value=_mock_response("hello"))

        session = GemmaMossSession(retriever=_mock_retriever())
        result = await session.ask("hi")

        assert result == "hello"
        mock.chat.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ask_executes_tool_call(self, MockClient):
        """When Gemma calls the tool, Moss is queried and results sent back."""
        mock = MockClient.return_value
        # First call: Gemma requests a tool call
        # Second call: Gemma answers with context
        mock.chat = AsyncMock(side_effect=[
            _mock_response(tool_calls=[_mock_tool_call("refund policy")]),
            _mock_response("Refunds take 5-7 days."),
        ])

        retriever = _mock_retriever("Refund policy: 30 days, 5-7 day processing.")
        session = GemmaMossSession(retriever=retriever)
        result = await session.ask("How do refunds work?")

        assert result == "Refunds take 5-7 days."
        retriever.retrieve.assert_awaited_once_with("refund policy")
        assert mock.chat.await_count == 2

    @pytest.mark.asyncio
    async def test_tool_call_no_results(self, MockClient):
        """When Moss returns no results, Gemma gets a 'no results' message."""
        mock = MockClient.return_value
        mock.chat = AsyncMock(side_effect=[
            _mock_response(tool_calls=[_mock_tool_call("obscure topic")]),
            _mock_response("I couldn't find information about that."),
        ])

        retriever = _mock_retriever(None)
        session = GemmaMossSession(retriever=retriever)
        result = await session.ask("What about obscure topic?")

        assert result == "I couldn't find information about that."
        # Verify the tool result sent back was the no-results message
        second_call = mock.chat.call_args_list[1]
        messages = second_call[1]["messages"] if "messages" in second_call[1] else second_call[0][0]
        tool_msg = [m for m in messages if m.get("role") == "tool"]
        assert len(tool_msg) == 1
        assert tool_msg[0]["content"] == "No relevant results found."

    @pytest.mark.asyncio
    async def test_tool_call_retrieval_failure(self, MockClient):
        """When Moss raises, Gemma gets an 'unavailable' message."""
        mock = MockClient.return_value
        mock.chat = AsyncMock(side_effect=[
            _mock_response(tool_calls=[_mock_tool_call("query")]),
            _mock_response("I'll answer without the knowledge base."),
        ])

        retriever = MagicMock()
        retriever.retrieve = AsyncMock(side_effect=RuntimeError("Moss down"))

        session = GemmaMossSession(retriever=retriever)
        result = await session.ask("question")

        assert result == "I'll answer without the knowledge base."
        second_call = mock.chat.call_args_list[1]
        messages = second_call[1]["messages"]
        tool_msg = [m for m in messages if m.get("role") == "tool"]
        assert tool_msg[0]["content"] == "Search is currently unavailable."

    @pytest.mark.asyncio
    async def test_history_persisted(self, MockClient):
        """Only user + final assistant turns are in history."""
        mock = MockClient.return_value
        mock.chat = AsyncMock(return_value=_mock_response("answer"))

        session = GemmaMossSession(retriever=_mock_retriever())
        await session.ask("question")

        history = session.get_history()
        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "question"}
        assert history[1] == {"role": "assistant", "content": "answer"}

    @pytest.mark.asyncio
    async def test_tool_call_not_in_history(self, MockClient):
        """Tool call turns are not persisted in history."""
        mock = MockClient.return_value
        mock.chat = AsyncMock(side_effect=[
            _mock_response(tool_calls=[_mock_tool_call("q")]),
            _mock_response("answer with context"),
        ])

        session = GemmaMossSession(retriever=_mock_retriever())
        await session.ask("question")

        history = session.get_history()
        assert len(history) == 2
        for msg in history:
            assert msg["role"] in ("user", "assistant")

    @pytest.mark.asyncio
    async def test_reset_clears_history(self, MockClient):
        """reset() empties history."""
        mock = MockClient.return_value
        mock.chat = AsyncMock(return_value=_mock_response("reply"))

        session = GemmaMossSession(retriever=_mock_retriever())
        await session.ask("hello")
        assert len(session.get_history()) == 2

        session.reset()
        assert len(session.get_history()) == 0

    @pytest.mark.asyncio
    async def test_get_history_returns_copy(self, MockClient):
        """get_history() returns a copy."""
        mock = MockClient.return_value
        mock.chat = AsyncMock(return_value=_mock_response("reply"))

        session = GemmaMossSession(retriever=_mock_retriever())
        await session.ask("hello")

        history = session.get_history()
        history.clear()
        assert len(session.get_history()) == 2

    @pytest.mark.asyncio
    async def test_constructor_copies_history(self, MockClient):
        """Constructor copies initial history."""
        initial = [{"role": "user", "content": "old"}]
        session = GemmaMossSession(retriever=_mock_retriever(), history=initial)

        initial.clear()
        assert len(session.get_history()) == 1

    @pytest.mark.asyncio
    async def test_tool_definition_includes_index_description(self, MockClient):
        """Tool description includes the index_description."""
        mock = MockClient.return_value
        mock.chat = AsyncMock(return_value=_mock_response("hi"))

        session = GemmaMossSession(
            retriever=_mock_retriever(),
            index_description="customer FAQ about orders and shipping",
        )
        await session.ask("hello")

        call_args = mock.chat.call_args
        tools = call_args[1]["tools"]
        desc = tools[0]["function"]["description"]
        assert "customer FAQ about orders and shipping" in desc

    @pytest.mark.asyncio
    async def test_custom_system_prompt(self, MockClient):
        """Custom system_prompt overrides the default."""
        mock = MockClient.return_value
        mock.chat = AsyncMock(return_value=_mock_response("reply"))

        session = GemmaMossSession(
            retriever=_mock_retriever(),
            system_prompt="Custom prompt.",
        )
        await session.ask("hello")

        call_args = mock.chat.call_args
        messages = call_args[1]["messages"]
        assert messages[0] == {"role": "system", "content": "Custom prompt."}

    @pytest.mark.asyncio
    async def test_ask_stream_yields_response(self, MockClient):
        """ask_stream() yields the complete response."""
        mock = MockClient.return_value
        mock.chat = AsyncMock(return_value=_mock_response("streamed reply"))

        session = GemmaMossSession(retriever=_mock_retriever())
        chunks = [c async for c in session.ask_stream("hello")]

        assert chunks == ["streamed reply"]

"""Tests for make_ollama_query_rewriter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gemma_moss.session import make_ollama_query_rewriter


class TestMakeOllamaQueryRewriter:
    """Tests for the Ollama query rewriter factory."""

    @pytest.mark.asyncio
    async def test_returns_rewritten_query(self):
        """Rewriter calls Ollama and returns the response content."""
        with patch("gemma_moss.session.AsyncClient") as MockOllama:
            mock_client = MagicMock()
            mock_client.chat = AsyncMock(return_value=MagicMock(
                message=MagicMock(content="  refined search query  ")
            ))
            MockOllama.return_value = mock_client

            rewriter = make_ollama_query_rewriter(model="gemma4")
            result = await rewriter("what about their refund policy?", [
                {"role": "user", "content": "Tell me about Acme Corp"},
                {"role": "assistant", "content": "Acme Corp is a retailer..."},
            ])

        assert result == "refined search query"

    @pytest.mark.asyncio
    async def test_includes_history_in_messages(self):
        """Rewriter sends conversation history to Ollama for context."""
        sent_messages = None

        with patch("gemma_moss.session.AsyncClient") as MockOllama:
            mock_client = MagicMock()

            async def capture_chat(**kwargs):
                nonlocal sent_messages
                sent_messages = kwargs.get("messages")
                return MagicMock(message=MagicMock(content="query"))

            mock_client.chat = capture_chat
            MockOllama.return_value = mock_client

            history = [{"role": "user", "content": "Prior turn"}]
            rewriter = make_ollama_query_rewriter(model="gemma4")
            await rewriter("current message", history)

        assert sent_messages is not None
        assert sent_messages[0]["role"] == "system"
        assert {"role": "user", "content": "Prior turn"} in sent_messages
        assert sent_messages[-1] == {"role": "user", "content": "current message"}

    @pytest.mark.asyncio
    async def test_custom_instruction(self):
        """Rewriter uses a custom instruction as the system prompt."""
        sent_messages = None

        with patch("gemma_moss.session.AsyncClient") as MockOllama:
            mock_client = MagicMock()

            async def capture_chat(**kwargs):
                nonlocal sent_messages
                sent_messages = kwargs.get("messages")
                return MagicMock(message=MagicMock(content="query"))

            mock_client.chat = capture_chat
            MockOllama.return_value = mock_client

            rewriter = make_ollama_query_rewriter(
                model="gemma4", instruction="Custom instruction"
            )
            await rewriter("message", [])

        assert sent_messages[0]["content"] == "Custom instruction"

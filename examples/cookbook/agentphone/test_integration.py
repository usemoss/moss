"""Unit tests for the Moss + AgentPhone bridge (no live API calls).

Tests cover:

- HMAC signature verification (accept valid, reject tampered, reject garbage).
- Tool-calling loop: model asks for moss_search, bridge runs Moss, model
  produces the final answer using the search result.
- Tool-calling loop: model can answer directly without calling the tool
  (e.g. small talk).
- Voice stream: emits the interim filler line then the final line.

Run with::

    uv run python test_integration.py
"""

from __future__ import annotations

import hashlib
import hmac
import json
import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from moss_agentphone import MossAgentPhoneBridge, verify_webhook_signature


class WebhookSignatureTests(unittest.TestCase):
    def test_accepts_valid_signature(self) -> None:
        secret = "whsec_test"
        timestamp = "1715760000"
        body = b'{"event":"agent.message"}'
        digest = hmac.new(
            secret.encode(),
            f"{timestamp}.".encode() + body,
            hashlib.sha256,
        ).hexdigest()
        self.assertTrue(
            verify_webhook_signature(
                secret=secret,
                timestamp=timestamp,
                body=body,
                signature=f"sha256={digest}",
            )
        )

    def test_rejects_tampered_body(self) -> None:
        secret = "whsec_test"
        timestamp = "1715760000"
        body = b'{"event":"agent.message"}'
        digest = hmac.new(
            secret.encode(),
            f"{timestamp}.".encode() + body,
            hashlib.sha256,
        ).hexdigest()
        self.assertFalse(
            verify_webhook_signature(
                secret=secret,
                timestamp=timestamp,
                body=b'{"event":"tampered"}',
                signature=f"sha256={digest}",
            )
        )

    def test_rejects_garbage_signature(self) -> None:
        self.assertFalse(
            verify_webhook_signature(
                secret="whsec_test",
                timestamp="1715760000",
                body=b"{}",
                signature="sha256=deadbeef",
            )
        )


def _text_block(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _tool_use_block(
    tool_id: str, name: str, args: dict[str, Any]
) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_id
    block.name = name
    block.input = args
    block.text = None
    return block


def _claude_response(stop_reason: str, content: list[Any]) -> MagicMock:
    response = MagicMock()
    response.stop_reason = stop_reason
    response.content = content
    return response


def _moss_with(docs: list[dict[str, Any]]) -> MagicMock:
    moss = MagicMock()
    doc_mocks = [
        MagicMock(
            text=d["text"],
            score=d.get("score"),
            metadata=d.get("metadata"),
        )
        for d in docs
    ]
    moss.query = AsyncMock(return_value=MagicMock(docs=doc_mocks))
    return moss


def _anthropic_client(responses: list[MagicMock]) -> MagicMock:
    client = MagicMock()
    client.messages.create = AsyncMock(side_effect=responses)
    return client


class BridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_tool_call_then_final_answer(self) -> None:
        moss = _moss_with(
            [{"text": "Refunds take 3-5 business days.", "score": 0.91}]
        )
        anthropic = _anthropic_client(
            [
                _claude_response(
                    "tool_use",
                    [
                        _tool_use_block(
                            "tu_1",
                            "moss_search",
                            {"query": "refund processing time"},
                        )
                    ],
                ),
                _claude_response(
                    "end_turn",
                    [_text_block("Refunds take three to five business days.")],
                ),
            ]
        )
        bridge = MossAgentPhoneBridge(
            moss_client=moss,
            index_name="demo",
            anthropic_client=anthropic,
        )

        answer = await bridge.run_tool_call("how long do refunds take?")

        self.assertEqual(
            answer, "Refunds take three to five business days."
        )
        moss.query.assert_awaited_once()
        passed_query = moss.query.await_args.args[1]
        self.assertEqual(passed_query, "refund processing time")
        # Second turn payload must include the tool_result content.
        second_call_messages = anthropic.messages.create.await_args_list[1].kwargs[
            "messages"
        ]
        tool_result_msg = second_call_messages[-1]
        self.assertEqual(tool_result_msg["role"], "user")
        self.assertEqual(tool_result_msg["content"][0]["type"], "tool_result")
        self.assertIn(
            "Refunds take 3-5 business days.",
            tool_result_msg["content"][0]["content"],
        )

    async def test_model_can_answer_without_tool(self) -> None:
        moss = _moss_with([])
        anthropic = _anthropic_client(
            [_claude_response("end_turn", [_text_block("Hi! How can I help?")])]
        )
        bridge = MossAgentPhoneBridge(
            moss_client=moss,
            index_name="demo",
            anthropic_client=anthropic,
        )

        answer = await bridge.run_tool_call("hello")

        self.assertEqual(answer, "Hi! How can I help?")
        moss.query.assert_not_awaited()

    async def test_voice_stream_emits_interim_then_final(self) -> None:
        moss = _moss_with([])
        anthropic = _anthropic_client(
            [
                _claude_response(
                    "end_turn",
                    [_text_block("You can return within thirty days.")],
                )
            ]
        )
        bridge = MossAgentPhoneBridge(
            moss_client=moss,
            index_name="demo",
            anthropic_client=anthropic,
        )

        chunks: list[dict[str, Any]] = []
        async for raw in bridge.voice_response_stream("can I return this?"):
            chunks.append(json.loads(raw.decode().strip()))

        self.assertEqual(len(chunks), 2)
        self.assertTrue(chunks[0].get("interim"))
        self.assertNotIn("interim", chunks[1])
        self.assertEqual(
            chunks[1]["text"], "You can return within thirty days."
        )


if __name__ == "__main__":
    unittest.main()

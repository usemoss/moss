"""Unit tests for the AgentPhone voice cookbook (no live API calls).

Tests:
- HMAC signature verification (accept valid, reject tampered/garbage).
- Tool-call loop: model asks for ``moss_search``, ``_moss_search`` runs Moss,
  model produces a grounded final answer using the returned excerpts.
- Tool-call loop: model can answer directly without calling the tool.
- ``_to_anthropic_history`` maps ``recentHistory`` into Anthropic messages
  with correct ``user``/``assistant`` roles.

Run with::

    uv run python test_integration.py
"""

from __future__ import annotations

import hashlib
import hmac
import os
import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("MOSS_PROJECT_ID", "test")
os.environ.setdefault("MOSS_PROJECT_KEY", "test")
os.environ.setdefault("MOSS_INDEX_NAME", "test-index")
os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("AGENTPHONE_WEBHOOK_SECRET", "whsec_test")

import server  # noqa: E402  (env must be set before import)


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
    return block


def _claude_response(stop_reason: str, content: list[Any]) -> MagicMock:
    response = MagicMock()
    response.stop_reason = stop_reason
    response.content = content
    return response


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
            server.verify_webhook_signature(
                secret=secret,
                timestamp=timestamp,
                body=body,
                signature=f"sha256={digest}",
            )
        )

    def test_rejects_tampered_body(self) -> None:
        secret = "whsec_test"
        timestamp = "1715760000"
        digest = hmac.new(
            secret.encode(),
            f"{timestamp}.".encode() + b'{"event":"agent.message"}',
            hashlib.sha256,
        ).hexdigest()
        self.assertFalse(
            server.verify_webhook_signature(
                secret=secret,
                timestamp=timestamp,
                body=b'{"event":"tampered"}',
                signature=f"sha256={digest}",
            )
        )

    def test_rejects_garbage_signature(self) -> None:
        self.assertFalse(
            server.verify_webhook_signature(
                secret="whsec_test",
                timestamp="1715760000",
                body=b"{}",
                signature="sha256=deadbeef",
            )
        )


class HistoryMappingTests(unittest.TestCase):
    def test_maps_directions_to_roles(self) -> None:
        history = server._to_anthropic_history(
            [
                {"content": "Hi", "direction": "inbound"},
                {"content": "Hello, how can I help?", "direction": "outbound"},
            ]
        )
        self.assertEqual(
            history,
            [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello, how can I help?"},
            ],
        )

    def test_skips_empty_entries(self) -> None:
        history = server._to_anthropic_history(
            [{"content": "", "direction": "inbound"}, None] if False else [
                {"content": "", "direction": "inbound"},
                {"content": "real", "direction": "outbound"},
            ]
        )
        self.assertEqual(
            history, [{"role": "assistant", "content": "real"}]
        )

    def test_empty_input_returns_empty_list(self) -> None:
        self.assertEqual(server._to_anthropic_history(None), [])
        self.assertEqual(server._to_anthropic_history([]), [])


class RunToolCallTests(unittest.IsolatedAsyncioTestCase):
    async def test_tool_call_then_final_answer(self) -> None:
        moss_result = MagicMock(
            docs=[MagicMock(text="Refunds take 3-5 business days.")]
        )
        responses = [
            _claude_response(
                "tool_use",
                [
                    _tool_use_block(
                        "tu_1", "moss_search", {"query": "refund processing time"}
                    )
                ],
            ),
            _claude_response(
                "end_turn",
                [_text_block("Refunds take three to five business days.")],
            ),
        ]

        with patch.object(
            server.moss_client, "query", AsyncMock(return_value=moss_result)
        ) as moss_query, patch.object(
            server.anthropic_client.messages,
            "create",
            AsyncMock(side_effect=responses),
        ) as anthropic_create:
            answer = await server.run_tool_call(
                "how long do refunds take?", history=[]
            )

        self.assertEqual(answer, "Refunds take three to five business days.")
        moss_query.assert_awaited_once()
        self.assertEqual(
            moss_query.await_args.args[1], "refund processing time"
        )
        # Second call must include the tool_result content.
        second_messages = anthropic_create.await_args_list[1].kwargs["messages"]
        self.assertEqual(second_messages[-1]["role"], "user")
        self.assertEqual(second_messages[-1]["content"][0]["type"], "tool_result")
        self.assertIn(
            "Refunds take 3-5 business days.",
            second_messages[-1]["content"][0]["content"],
        )

    async def test_model_can_answer_without_tool(self) -> None:
        responses = [
            _claude_response("end_turn", [_text_block("Hi! How can I help?")])
        ]
        with patch.object(
            server.moss_client, "query", AsyncMock()
        ) as moss_query, patch.object(
            server.anthropic_client.messages,
            "create",
            AsyncMock(side_effect=responses),
        ):
            answer = await server.run_tool_call("hello", history=[])

        self.assertEqual(answer, "Hi! How can I help?")
        moss_query.assert_not_awaited()

    async def test_history_is_prepended_to_messages(self) -> None:
        responses = [_claude_response("end_turn", [_text_block("ok")])]
        history = [
            {"role": "user", "content": "earlier turn"},
            {"role": "assistant", "content": "earlier reply"},
        ]
        with patch.object(server.moss_client, "query", AsyncMock()), patch.object(
            server.anthropic_client.messages,
            "create",
            AsyncMock(side_effect=responses),
        ) as anthropic_create:
            await server.run_tool_call("new turn", history=history)

        sent = anthropic_create.await_args.kwargs["messages"]
        self.assertEqual(sent[0], {"role": "user", "content": "earlier turn"})
        self.assertEqual(sent[1], {"role": "assistant", "content": "earlier reply"})
        self.assertEqual(sent[2], {"role": "user", "content": "new turn"})


if __name__ == "__main__":
    unittest.main()

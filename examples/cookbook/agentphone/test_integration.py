"""Unit tests for the AgentPhone voice cookbook (no live API calls).

Tests:
- HMAC signature verification (accept valid, reject tampered/garbage).
- ``to_anthropic_history`` maps ``recentHistory`` into Anthropic messages
  with correct ``user`` / ``assistant`` roles.
- Tool-call loop: model asks for ``moss_search``, the handler runs Moss,
  model produces a grounded final answer using the returned excerpts.
- Tool-call loop: model can answer directly without calling the tool.
- Tool-call loop: ``history`` is prepended to the messages sent to Claude.

Run with::

    uv run python test_integration.py
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from moss_agentphone import (
    run_tool_call,
    to_anthropic_history,
    verify_webhook_signature,
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
    return block


def _claude_response(stop_reason: str, content: list[Any]) -> MagicMock:
    response = MagicMock()
    response.stop_reason = stop_reason
    response.content = content
    return response


def _anthropic_client(responses: list[MagicMock]) -> MagicMock:
    client = MagicMock()
    client.messages.create = AsyncMock(side_effect=responses)
    return client


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
        digest = hmac.new(
            secret.encode(),
            f"{timestamp}.".encode() + b'{"event":"agent.message"}',
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


class HistoryMappingTests(unittest.TestCase):
    def test_maps_directions_to_roles(self) -> None:
        history = to_anthropic_history(
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
        history = to_anthropic_history(
            [
                {"content": "", "direction": "inbound"},
                {"content": "real", "direction": "outbound"},
            ]
        )
        self.assertEqual(
            history, [{"role": "assistant", "content": "real"}]
        )

    def test_empty_input_returns_empty_list(self) -> None:
        self.assertEqual(to_anthropic_history(None), [])
        self.assertEqual(to_anthropic_history([]), [])


class RunToolCallTests(unittest.IsolatedAsyncioTestCase):
    async def test_tool_call_then_final_answer(self) -> None:
        async def moss_search(args: dict[str, Any]) -> str:
            return f"1. excerpt about {args['query']}"

        anthropic = _anthropic_client(
            [
                _claude_response(
                    "tool_use",
                    [
                        _tool_use_block(
                            "tu_1", "moss_search", {"query": "refunds"}
                        )
                    ],
                ),
                _claude_response(
                    "end_turn",
                    [_text_block("Refunds take three to five business days.")],
                ),
            ]
        )

        answer = await run_tool_call(
            user_message="how long do refunds take?",
            history=[],
            anthropic_client=anthropic,
            tool_handlers={"moss_search": moss_search},
            model="claude-haiku-4-5-20251001",
            system_prompt="You are a test agent.",
        )

        self.assertEqual(answer, "Refunds take three to five business days.")
        # Second Anthropic call must include the tool_result content.
        second_messages = anthropic.messages.create.await_args_list[1].kwargs[
            "messages"
        ]
        self.assertEqual(second_messages[-1]["role"], "user")
        self.assertEqual(second_messages[-1]["content"][0]["type"], "tool_result")
        self.assertIn(
            "excerpt about refunds",
            second_messages[-1]["content"][0]["content"],
        )

    async def test_model_can_answer_without_tool(self) -> None:
        called = False

        async def moss_search(args: dict[str, Any]) -> str:
            nonlocal called
            called = True
            return ""

        anthropic = _anthropic_client(
            [_claude_response("end_turn", [_text_block("Hi! How can I help?")])]
        )

        answer = await run_tool_call(
            user_message="hello",
            history=[],
            anthropic_client=anthropic,
            tool_handlers={"moss_search": moss_search},
            model="claude-haiku-4-5-20251001",
            system_prompt="You are a test agent.",
        )

        self.assertEqual(answer, "Hi! How can I help?")
        self.assertFalse(called)

    async def test_history_is_prepended_to_messages(self) -> None:
        anthropic = _anthropic_client(
            [_claude_response("end_turn", [_text_block("ok")])]
        )
        history = [
            {"role": "user", "content": "earlier turn"},
            {"role": "assistant", "content": "earlier reply"},
        ]

        await run_tool_call(
            user_message="new turn",
            history=history,
            anthropic_client=anthropic,
            tool_handlers={},
            model="claude-haiku-4-5-20251001",
            system_prompt="You are a test agent.",
        )

        sent = anthropic.messages.create.await_args.kwargs["messages"]
        self.assertEqual(sent[0], {"role": "user", "content": "earlier turn"})
        self.assertEqual(
            sent[1], {"role": "assistant", "content": "earlier reply"}
        )
        self.assertEqual(sent[2], {"role": "user", "content": "new turn"})


if __name__ == "__main__":
    unittest.main()

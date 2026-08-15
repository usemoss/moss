"""Regression for the retrieval note after a failed second search in a turn.

extension.py imports the TEN runtime, which is not installed offline, so we load
just that one file against light stubs and drive its Moss methods directly.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

EXTENSION = (
    Path(__file__).resolve().parents[1]
    / "tenapp"
    / "ten_packages"
    / "extension"
    / "main_python"
    / "extension.py"
)


def _load_extension_module():
    pkg = "main_python"

    def stub(name: str) -> types.ModuleType:
        mod = types.ModuleType(name)
        sys.modules[name] = mod
        return mod

    runtime = stub("ten_runtime")
    for symbol in ("AsyncTenEnv", "Cmd", "Data"):
        setattr(runtime, symbol, type(symbol, (), {}))
    runtime.AsyncExtension = type(
        "AsyncExtension", (), {"__init__": lambda self, name: None}
    )
    runtime.StatusCode = type("StatusCode", (), {"OK": "ok"})

    class _CmdResult:
        def __init__(self):
            self.content = None

        @classmethod
        def create(cls, _status, _cmd):
            return cls()

        def set_property_from_json(self, _key, value):
            self.content = value

    runtime.CmdResult = _CmdResult

    ten_moss = stub("ten_moss")
    ten_moss.MossSessionManager = type("MossSessionManager", (), {})

    const = stub("ten_ai_base.const")
    const.CMD_PROPERTY_RESULT = "result"
    ai_types = stub("ten_ai_base.types")
    ai_types.LLMToolMetadata = type("LLMToolMetadata", (), {})
    ai_types.LLMToolMetadataParameter = type("LLMToolMetadataParameter", (), {})
    ai_base = stub("ten_ai_base")
    ai_base.const = const
    ai_base.types = ai_types

    parent = stub(pkg)
    parent.__path__ = []
    agent_pkg = stub(f"{pkg}.agent")
    agent_pkg.__path__ = []
    decorators = stub(f"{pkg}.agent.decorators")
    decorators.agent_event_handler = lambda *a, **k: (lambda fn: fn)
    agent_mod = stub(f"{pkg}.agent.agent")
    agent_mod.Agent = type("Agent", (), {})
    events = stub(f"{pkg}.agent.events")
    for evt in (
        "ASRResultEvent",
        "LLMResponseEvent",
        "ToolRegisterEvent",
        "UserJoinedEvent",
        "UserLeftEvent",
    ):
        setattr(events, evt, type(evt, (), {}))
    helper = stub(f"{pkg}.helper")
    helper._send_cmd = helper._send_data = lambda *a, **k: None
    helper.parse_sentences = lambda frag, delta: ([], "")
    config = stub(f"{pkg}.config")
    config.MainControlConfig = type("MainControlConfig", (), {})

    spec = importlib.util.spec_from_file_location(f"{pkg}.extension", EXTENSION)
    module = importlib.util.module_from_spec(spec)
    module.__package__ = pkg
    spec.loader.exec_module(module)
    return module


extension = _load_extension_module()


class _RecordingEnv:
    def __init__(self):
        self.results = []

    def log_info(self, *_a):
        pass

    def log_error(self, *_a):
        pass

    async def return_result(self, result):
        self.results.append(result)


class _FlakyMoss:
    """Succeeds once, then raises - a second search failing mid-turn."""

    last_time_taken_ms = 12

    def __init__(self):
        self.calls = 0

    async def query_context(self, _text: str) -> str:
        self.calls += 1
        if self.calls == 1:
            return "Refunds land in 3-5 business days."
        raise RuntimeError("moss backend unavailable")


class _ToolCallCmd:
    """A tool_call Cmd carrying a search_knowledge_base payload."""

    def __init__(self, query: str):
        self._raw = json.dumps(
            {"name": "search_knowledge_base", "arguments": {"query": query}}
        )

    def get_property_to_json(self, _key):
        return self._raw, None


@pytest.mark.asyncio
async def test_failed_second_search_does_not_replay_first_hit() -> None:
    ext = extension.MainControlExtension("main_control")
    ext.ten_env = _RecordingEnv()
    ext.moss = _FlakyMoss()

    notes: list[str] = []

    async def capture(role, text, final, stream_id, data_type="text"):
        notes.append(text)

    ext._send_transcript = capture

    # Drive the real tool-call handler so the note reflects production flow.
    await ext._on_tool_call(_ToolCallCmd("How long do refunds take?"))
    assert "3-5 business days" in notes[0]
    assert "3-5 business days" in ext.ten_env.results[0].content

    await ext._on_tool_call(_ToolCallCmd("What about exchanges?"))

    # Second search failed: the note must not replay the first hit, and the
    # tool result is empty - the two must agree.
    assert "3-5 business days" not in notes[1]
    assert "no match" in notes[1]
    assert '"content": ""' in ext.ten_env.results[1].content
    assert ext._last_grounding == ""
    assert ext._last_sdk_ms is None

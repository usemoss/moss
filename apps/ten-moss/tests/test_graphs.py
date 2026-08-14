"""Contract tests for the two TEN graphs. No TEN runtime, no Moss creds."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

TENAPP = Path(__file__).resolve().parents[1] / "tenapp"
EXTENSION = TENAPP / "ten_packages" / "extension" / "main_python"
PROPERTY = TENAPP / "property.json"


@pytest.fixture(scope="module")
def graphs() -> list[dict]:
    payload = json.loads(PROPERTY.read_text())
    return payload["ten"]["predefined_graphs"]


def _main_control(graph: dict) -> dict:
    nodes = graph["graph"]["nodes"]
    matches = [n for n in nodes if n.get("name") == "main_control"]
    assert len(matches) == 1
    return matches[0]


def test_default_graph_is_ambient_voice_assistant(graphs: list[dict]) -> None:
    names = [g["name"] for g in graphs]
    assert names[0] == "voice_assistant"
    ambient = graphs[0]
    assert ambient["auto_start"] is True
    props = _main_control(ambient)["property"]
    assert props["enable_moss"] is True
    assert props.get("moss_mode", "ambient") == "ambient"


def test_tool_graph_is_selectable_and_not_default(graphs: list[dict]) -> None:
    by_name = {g["name"]: g for g in graphs}
    assert "voice_assistant_tools" in by_name
    tool = by_name["voice_assistant_tools"]
    assert tool["auto_start"] is False
    props = _main_control(tool)["property"]
    assert props["moss_mode"] == "tool"
    assert props["enable_moss"] is True


def test_ambient_prepend_and_tool_handler_are_visible() -> None:
    src = (EXTENSION / "extension.py").read_text()
    assert "query_context" in src
    assert "[Current User Question]" in src
    assert "moss_mode_prepends_on_asr" in src
    assert "search_knowledge_base" in src
    assert 'cmd.get_name() == "tool_call"' in src
    # Ambient prepend must stay gated on moss_mode, not deleted.
    assert "moss_mode_prepends_on_asr" in (EXTENSION / "config.py").read_text()


def test_config_helper_skips_prepend_in_tool_mode() -> None:
    src = (EXTENSION / "config.py").read_text()
    assert "def moss_mode_prepends_on_asr" in src
    assert "return moss_mode != MOSS_MODE_TOOL" in src
    assert 'moss_mode: Literal["ambient", "tool"] = MOSS_MODE_AMBIENT' in src

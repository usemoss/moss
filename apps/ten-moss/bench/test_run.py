"""Unit tests for the offline bench. No Moss creds, no LLM keys."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run import (
    LocalCorpusSearch,
    contains_gold,
    echo_answer,
    load_queries,
    render_table,
    run_bench,
    score_row,
)


def test_queries_cover_ten_faqs() -> None:
    rows = load_queries()
    assert len(rows) == 10
    ids = [r["id"] for r in rows]
    assert ids == [f"kb-{i}" for i in range(1, 11)]
    assert rows[0]["query"] == "How long do refunds take?"
    assert "3-5" in rows[0]["gold"]
    assert "Visa" in rows[5]["gold"]


def test_contains_gold_any_phrase() -> None:
    assert contains_gold("We accept Visa and cash", ["Visa", "PayPal", "Apple Pay"])
    assert not contains_gold("we take cash only", ["Visa", "PayPal", "Apple Pay"])


@pytest.mark.asyncio
async def test_echo_grounding_scores_three_arms() -> None:
    grounding = "Relevant knowledge from Moss:\n\n[1] Refunds are processed within 3-5 business days."

    async def search(query: str):
        return grounding, 2.0, 8.0

    query = {
        "id": "kb-1",
        "query": "How long do refunds take?",
        "gold": ["3-5"],
    }
    ambient = score_row(
        query,
        await echo_answer(arm="ambient", query=query["query"], search=search, always_call_tool=True),
        "ambient",
    )
    tool = score_row(
        query,
        await echo_answer(arm="tool", query=query["query"], search=search, always_call_tool=True),
        "tool",
    )
    none = score_row(
        query,
        await echo_answer(arm="no-moss", query=query["query"], search=search, always_call_tool=True),
        "no-moss",
    )
    assert ambient["hit"] and ambient["faithful"]
    assert tool["hit"] and tool["faithful"] and tool["tool_called"]
    assert not none["hit"] and not none["faithful"]
    assert none["moss_retrieval_ms"] is None


@pytest.mark.asyncio
async def test_moss_error_fail_open() -> None:
    async def boom(query: str):
        raise RuntimeError("timeout")

    # echo_answer itself should not raise; MossSearch catches. Simulate empty.
    result = await echo_answer(
        arm="ambient",
        query="How long do refunds take?",
        search=AsyncMock(return_value=("", None, None)),
        always_call_tool=True,
    )
    scored = score_row(
        {"id": "kb-1", "query": "q", "gold": ["3-5"]},
        result,
        "ambient",
    )
    assert scored["hit"] is False
    assert scored["faithful"] is False
    _ = boom  # kept so a later mutation can swap search=boom and expect no raise


@pytest.mark.asyncio
async def test_echo_answer_swallows_search_error_via_wrapper() -> None:
    from run import MossSearch

    class Broken:
        last_time_taken_ms = None

        async def query_context(self, text: str) -> str:
            raise TimeoutError("nope")

    result = await MossSearch(Broken()).search("How long do refunds take?")
    assert result[0] == ""


@pytest.mark.asyncio
async def test_run_echo_grounding_prints_table(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    rows = await run_bench(echo_grounding=True, json_out=tmp_path / "out.json")
    assert len(rows) == 30  # 10 queries x 3 arms
    out = capsys.readouterr().out
    assert "| query | arm |" in out
    assert "How long do refunds take?" in out
    assert "### Summary" in out
    saved = json.loads((tmp_path / "out.json").read_text())
    assert len(saved) == 30


@pytest.mark.asyncio
async def test_local_corpus_hits_refunds() -> None:
    from run import load_knowledge

    block, sdk, wall = await LocalCorpusSearch(load_knowledge(), load_queries()).search(
        "How long do refunds take?"
    )
    assert "3-5" in block
    assert sdk is None and wall is None


def test_render_table_includes_all_arms() -> None:
    table = render_table(
        [
            {
                "query": "q",
                "arm": "ambient",
                "moss_retrieval_ms": 2,
                "moss_wall_ms": 9,
                "hit": True,
                "faithful": True,
                "tool_called": False,
            },
            {
                "query": "q",
                "arm": "tool",
                "moss_retrieval_ms": 2,
                "moss_wall_ms": 9,
                "hit": True,
                "faithful": True,
                "tool_called": True,
            },
            {
                "query": "q",
                "arm": "no-moss",
                "moss_retrieval_ms": None,
                "moss_wall_ms": None,
                "hit": False,
                "faithful": False,
                "tool_called": False,
            },
        ]
    )
    assert "ambient" in table and "tool" in table and "no-moss" in table

"""Unit tests for the offline bench. No Moss creds, no LLM keys."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run import (
    contains_gold,
    load_queries,
    lookup_faq,
    query_moss,
    render_table,
    run_bench,
    run_one,
)


def test_queries_cover_ten_faqs() -> None:
    rows = load_queries()
    assert len(rows) == 10
    assert [r["id"] for r in rows] == [f"kb-{i}" for i in range(1, 11)]
    assert rows[0]["query"] == "How long do refunds take?"
    assert "Refunds are processed" in rows[0]["gold"]
    assert "Standard shipping" in rows[3]["gold"]
    assert rows[0]["gold"] != rows[3]["gold"]
    assert "Visa" in rows[5]["gold"]


def test_contains_gold_any_phrase() -> None:
    assert contains_gold("We accept Visa and cash", ["Visa", "PayPal", "Apple Pay"])
    assert not contains_gold("we take cash only", ["Visa", "PayPal", "Apple Pay"])


@pytest.mark.asyncio
async def test_three_arms_with_echo() -> None:
    queries = load_queries()
    docs = [{"id": "kb-1", "text": "Refunds are processed within 3-5 business days."}]
    query = "How long do refunds take?"
    gold = ["Refunds are processed"]
    ambient = await run_one("ambient", query, gold, "kb-1", None, queries, docs)
    tool = await run_one("tool", query, gold, "kb-1", None, queries, docs)
    none = await run_one("no-moss", query, gold, "kb-1", None, queries, docs)
    assert ambient["hit"] and ambient["faithful"]
    assert tool["hit"] and tool["faithful"] and tool["tool_called"]
    assert not none["hit"] and not none["faithful"]


@pytest.mark.asyncio
async def test_query_moss_fail_open() -> None:
    class Broken:
        last_time_taken_ms = None

        async def query_context(self, text: str) -> str:
            raise TimeoutError("nope")

    context, sdk_ms, _wall = await query_moss(Broken(), "How long do refunds take?")
    assert context == ""
    assert sdk_ms is None


@pytest.mark.asyncio
async def test_hit_requires_gold_phrase_not_doc_id() -> None:
    class IdOnly:
        last_time_taken_ms = 1

        async def query_context(self, text: str) -> str:
            return "kb-1"

    row = await run_one(
        "ambient",
        "How long do refunds take?",
        ["Refunds are processed"],
        "kb-1",
        IdOnly(),
        [],
        [],
    )
    assert row["hit"] is False
    assert row["faithful"] is False


@pytest.fixture
def offline_moss(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("run.load_dotenv", lambda *_a, **_k: False)
    for key in ("MOSS_PROJECT_ID", "MOSS_PROJECT_KEY", "MOSS_INDEX_NAME", "MOSS_MODEL_ID"):
        monkeypatch.delenv(key, raising=False)


@pytest.mark.asyncio
async def test_run_echo_grounding_prints_table(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, offline_moss
) -> None:
    rows = await run_bench(json_out=tmp_path / "out.json")
    assert len(rows) == 30
    out = capsys.readouterr().out
    assert "| query | arm |" in out
    assert "How long do refunds take?" in out
    assert "### Summary" in out
    assert len(json.loads((tmp_path / "out.json").read_text())) == 30


def test_lookup_faq_hits_refunds() -> None:
    queries = load_queries()
    docs = [
        {
            "id": "kb-1",
            "text": "Refunds are processed within 3-5 business days once the return is approved.",
        }
    ]
    block = lookup_faq("How long do refunds take?", queries, docs)
    assert "3-5" in block


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

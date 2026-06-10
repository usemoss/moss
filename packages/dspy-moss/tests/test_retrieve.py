from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from dspy_moss import MossRM


@dataclass
class FakeDoc:
    id: str
    text: str
    score: float
    metadata: dict[str, str] | None = None


@dataclass
class FakeResult:
    docs: list[FakeDoc]


class FakeMossClient:
    def __init__(self) -> None:
        self.queries: list[dict[str, Any]] = []
        self.load_calls: list[dict[str, Any]] = []

    async def query(self, index_name: str, query: str, options: Any) -> FakeResult:
        self.queries.append({"index_name": index_name, "query": query, "options": options})
        return FakeResult(
            docs=[
                FakeDoc(
                    id=f"{query}-1",
                    text=f"passage for {query}",
                    score=0.91,
                    metadata={"source": "unit-test"},
                )
            ]
        )

    async def load_index(
        self,
        index_name: str,
        auto_refresh: bool = False,
        polling_interval_in_seconds: int = 600,
    ) -> str:
        self.load_calls.append(
            {
                "index_name": index_name,
                "auto_refresh": auto_refresh,
                "polling_interval_in_seconds": polling_interval_in_seconds,
            }
        )
        return index_name


def test_forward_returns_dspy_passage_objects_and_query_options() -> None:
    client = FakeMossClient()
    rm = MossRM(index_name="support-kb", moss_client=client, k=3, alpha=0.8)

    try:
        passages = rm.forward("refund policy", k=5, alpha=0.25, filter={"tier": "pro"})
    finally:
        rm.close()

    assert len(passages) == 1
    assert passages[0].long_text == "passage for refund policy"
    assert passages[0]["long_text"] == "passage for refund policy"
    assert passages[0].id == "refund policy-1"
    assert passages[0].score == 0.91
    assert passages[0].metadata == {"source": "unit-test"}

    assert client.queries[0]["index_name"] == "support-kb"
    assert client.queries[0]["query"] == "refund policy"
    options = client.queries[0]["options"]
    assert options.top_k == 5
    assert options.alpha == 0.25
    assert options.filter == {"tier": "pro"}


def test_forward_handles_multiple_queries_and_skips_empty_queries() -> None:
    client = FakeMossClient()
    rm = MossRM(index_name="support-kb", moss_client=client, k=2)

    try:
        passages = rm.forward(["refund policy", "", "payment methods"])
    finally:
        rm.close()

    assert [call["query"] for call in client.queries] == ["refund policy", "payment methods"]
    assert [passage.long_text for passage in passages] == [
        "passage for refund policy",
        "passage for payment methods",
    ]
    assert all(call["options"].top_k == 2 for call in client.queries)
    assert all(call["options"].alpha == pytest.approx(0.8) for call in client.queries)


@pytest.mark.asyncio
async def test_forward_inside_running_event_loop_reuses_executor() -> None:
    client = FakeMossClient()
    rm = MossRM(index_name="support-kb", moss_client=client)
    executor = rm._executor

    try:
        first = rm.forward("first")
        second = rm.forward("second")
    finally:
        rm.close()

    assert rm._executor is executor
    assert [call["query"] for call in client.queries] == ["first", "second"]
    assert first[0].long_text == "passage for first"
    assert second[0].long_text == "passage for second"


def test_load_index_forwards_refresh_options() -> None:
    client = FakeMossClient()
    rm = MossRM(index_name="support-kb", moss_client=client)

    try:
        rm.load_index(auto_refresh=True, polling_interval_in_seconds=120)
    finally:
        rm.close()

    assert client.load_calls == [
        {
            "index_name": "support-kb",
            "auto_refresh": True,
            "polling_interval_in_seconds": 120,
        }
    ]

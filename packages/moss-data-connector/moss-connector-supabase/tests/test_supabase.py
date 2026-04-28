from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("supabase")

from moss import DocumentInfo  # noqa: E402
from moss_connector_supabase import SupabaseConnector, ingest  # noqa: E402


@dataclass
class FakeMutationResult:
    doc_count: int
    job_id: str = "fake-job-id"
    index_name: str = ""


@dataclass
class FakeMossClient:
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def create_index(self, name, docs, model_id=None):
        docs = list(docs)
        self.calls.append({"name": name, "docs": docs, "model_id": model_id})
        return FakeMutationResult(doc_count=len(docs), index_name=name)


def _supabase_mock_paginating(pages: list[list[dict[str, Any]]]) -> MagicMock:
    """Build a mock supabase client whose
    ``.table().select().range().execute()`` chain returns successive pages.

    After all pages are exhausted, returns an empty page so the connector's
    ``while True`` loop terminates safely even if length-based exit conditions
    don't fire (e.g. final page exactly equals page_size).
    """
    responses = [MagicMock(data=p) for p in pages] + [MagicMock(data=[])]
    range_mock = MagicMock()
    range_mock.execute.side_effect = responses

    select_mock = MagicMock()
    select_mock.range.return_value = range_mock

    table_mock = MagicMock()
    table_mock.select.return_value = select_mock

    client = MagicMock()
    client.table.return_value = table_mock
    return client


async def test_supabase_ingest_end_to_end():
    rows_from_supabase = [
        {"id": 1, "title": "Refund policy", "body": "Refunds take 3–5 days."},
        {"id": 2, "title": "Shipping", "body": "We ship within 24 hours."},
        {"id": 3, "title": "Returns", "body": "Returns accepted within 30 days."},
    ]
    fake_client = _supabase_mock_paginating([rows_from_supabase])
    fake_moss = FakeMossClient()

    with (
        patch(
            "moss_connector_supabase.connector.create_client",
            return_value=fake_client,
        ),
        patch(
            "moss_connector_supabase.ingest.MossClient",
            return_value=fake_moss,
        ),
    ):
        source = SupabaseConnector(
            url="https://x.supabase.co",
            key="anon",
            table="articles",
            mapper=lambda r: DocumentInfo(
                id=str(r["id"]),
                text=r["body"],
                metadata={"title": r["title"]},
            ),
        )
        result = await ingest(source, "fake_id", "fake_key", index_name="articles")

    assert result is not None
    assert result.doc_count == 3
    assert len(fake_moss.calls) == 1

    moss_docs = fake_moss.calls[0]["docs"]
    assert moss_docs[0].id == "1"
    assert moss_docs[0].text == "Refunds take 3–5 days."
    assert moss_docs[0].metadata == {"title": "Refund policy"}
    assert moss_docs[2].id == "3"


async def test_pagination_advances_range_cursor():
    """With a small page_size, the connector should request successive ranges
    until a short page (or empty page) signals end of data."""
    page1 = [{"id": i, "body": f"row {i}"} for i in range(2)]
    page2 = [{"id": i, "body": f"row {i}"} for i in range(2, 3)]  # short, ends loop
    fake_client = _supabase_mock_paginating([page1, page2])
    fake_moss = FakeMossClient()

    with (
        patch(
            "moss_connector_supabase.connector.create_client",
            return_value=fake_client,
        ),
        patch(
            "moss_connector_supabase.ingest.MossClient",
            return_value=fake_moss,
        ),
    ):
        source = SupabaseConnector(
            url="https://x.supabase.co",
            key="anon",
            table="t",
            mapper=lambda r: DocumentInfo(id=str(r["id"]), text=r["body"]),
            page_size=2,
        )
        result = await ingest(source, "fake_id", "fake_key", "t")

    assert result.doc_count == 3
    moss_docs = fake_moss.calls[0]["docs"]
    assert [d.id for d in moss_docs] == ["0", "1", "2"]

    # Verify range() was called with advancing offsets: (0, 1), (2, 3).
    range_calls = fake_client.table.return_value.select.return_value.range.call_args_list
    assert range_calls[0].args == (0, 1)
    assert range_calls[1].args == (2, 3)


async def test_empty_result_skips_network_call():
    fake_client = _supabase_mock_paginating([])
    fake_moss = FakeMossClient()

    with (
        patch(
            "moss_connector_supabase.connector.create_client",
            return_value=fake_client,
        ),
        patch(
            "moss_connector_supabase.ingest.MossClient",
            return_value=fake_moss,
        ),
    ):
        source = SupabaseConnector(
            url="https://x.supabase.co",
            key="anon",
            table="empty",
            mapper=lambda r: DocumentInfo(id=str(r["id"]), text=""),
        )
        result = await ingest(source, "fake_id", "fake_key", "empty")

    assert result is None
    assert fake_moss.calls == []


async def test_select_kwarg_forwarded():
    """The ``select`` kwarg should be passed straight through to
    PostgREST's ``.select()``."""
    fake_client = _supabase_mock_paginating([])

    with patch(
        "moss_connector_supabase.connector.create_client",
        return_value=fake_client,
    ):
        source = SupabaseConnector(
            url="https://x.supabase.co",
            key="anon",
            table="t",
            mapper=lambda r: DocumentInfo(id="x", text="y"),
            select="id,body,title",
        )
        list(source)  # exhaust to trigger the call

    fake_client.table.return_value.select.assert_called_once_with("id,body,title")

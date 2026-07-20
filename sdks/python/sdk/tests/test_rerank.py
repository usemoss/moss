from unittest.mock import MagicMock, patch

import pytest

from moss import QueryResultDocumentInfo, SearchResult
from moss.client.moss_client import MossClient, QueryOptions


def test_query_options_validation():
    # Test valid options
    opts = QueryOptions(
        top_k=5, alpha=0.5, embedding=[0.1, 0.2], rerank=True, rerank_top_k=10
    )
    assert opts.top_k == 5
    assert opts.alpha == 0.5
    assert opts.embedding == [0.1, 0.2]
    assert opts.rerank is True
    assert opts.rerank_top_k == 10

    # Test invalid top_k
    with pytest.raises(ValueError, match="top_k must be an integer >= 1"):
        QueryOptions(top_k=-1)

    # Test invalid alpha
    with pytest.raises(ValueError, match="alpha must be a float between 0.0 and 1.0"):
        QueryOptions(alpha=2.0)

    # Test invalid embedding
    with pytest.raises(ValueError, match="embedding must be a sequence of numbers"):
        QueryOptions(embedding=["invalid"])  # type: ignore

    # Test invalid rerank_top_k
    with pytest.raises(ValueError, match="rerank_top_k must be an integer >= 1"):
        QueryOptions(rerank_top_k=0)


@pytest.mark.asyncio
async def test_rerank_results():
    client = MossClient("test", "key")

    # Create fake docs
    doc1 = QueryResultDocumentInfo(id="1", text="Bad match", score=0.9)
    doc2 = QueryResultDocumentInfo(id="2", text="Good match", score=0.8)
    doc3 = QueryResultDocumentInfo(id="3", text="Okay match", score=0.85)

    search_result = SearchResult(
        docs=[doc1, doc2, doc3], query="test query", index_name="idx", time_taken_ms=10
    )

    opts = QueryOptions(top_k=2, rerank=True, rerank_model="mock-model")

    # We need to mock sentence_transformers.CrossEncoder
    mock_model = MagicMock()
    # Let's say the cross encoder scores doc2 the highest, then doc3, then doc1
    mock_model.predict.return_value = [0.1, 0.99, 0.5]

    with patch.dict(
        "sys.modules",
        {
            "sentence_transformers": MagicMock(
                CrossEncoder=MagicMock(return_value=mock_model)
            )
        },
    ):
        result = await client._rerank_results("test query", search_result, opts)

        # It should slice to top_k=2, so doc1 should be dropped
        assert len(result.docs) == 2

        # First should be doc2
        assert result.docs[0].id == "2"
        assert result.docs[0].score == pytest.approx(0.99, abs=1e-5)

        # Second should be doc3
        assert result.docs[1].id == "3"
        assert result.docs[1].score == pytest.approx(0.5, abs=1e-5)

        # Ensure predict was called with pairs
        mock_model.predict.assert_called_once_with(
            [
                ["test query", "Bad match"],
                ["test query", "Good match"],
                ["test query", "Okay match"],
            ]
        )

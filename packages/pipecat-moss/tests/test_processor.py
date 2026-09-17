"""Tests for MossIndexProcessor and MossRetrievalService."""

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest
from pipecat.frames.frames import Frame, LLMContextFrame, LLMMessagesUpdateFrame
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection

from pipecat_moss.moss_index_processor import MossIndexProcessor
from pipecat_moss.moss_retrieval_service import MossRetrievalService


@dataclass
class FakeDoc:
    text: str
    score: float | None = None
    metadata: dict | None = None


def make_processor(**kwargs) -> MossIndexProcessor:
    """Helper to instantiate MossIndexProcessor with a mocked MossClient."""
    mock_client = MagicMock()
    defaults = {
        "client": mock_client,
        "index_name": "test-index",
        "top_k": 3,
        "alpha": 0.7,
        "system_prompt": "Retrieved context:\n\n",
    }
    defaults.update(kwargs)
    return MossIndexProcessor(**defaults)


class TestMossRetrievalService:
    def test_init_service(self):
        service = MossRetrievalService(
            project_id="pid",
            project_key="pkey",
            system_prompt="Custom context:\n\n",
        )
        assert service._system_prompt == "Custom context:\n\n"
        assert service._client is not None

    @pytest.mark.asyncio
    async def test_load_index(self):
        service = MossRetrievalService(project_id="pid", project_key="pkey")
        service._client.load_index = AsyncMock(return_value=None)

        await service.load_index("kb-index")
        service._client.load_index.assert_awaited_once_with("kb-index")

    def test_query_creates_processor(self):
        service = MossRetrievalService(project_id="pid", project_key="pkey")
        processor = service.query("support-index", top_k=7, alpha=0.5)

        assert isinstance(processor, MossIndexProcessor)
        assert processor._index_name == "support-index"
        assert processor._top_k == 7
        assert processor._alpha == 0.5


class TestFormatDocuments:
    def test_formats_text_only(self):
        processor = make_processor()
        docs = [FakeDoc(text="Paris is the capital of France.")]
        result = processor._format_documents(docs)
        assert result == "Retrieved context:\n\n1. Paris is the capital of France."

    def test_formats_with_source_and_score(self):
        processor = make_processor()
        docs = [FakeDoc(text="Info", score=0.91, metadata={"source": "geo.md"})]
        result = processor._format_documents(docs)
        assert result == "Retrieved context:\n\n1. Info (source=geo.md, score=0.91)"

    def test_empty_documents(self):
        processor = make_processor()
        result = processor._format_documents([])
        assert result == "Retrieved context:"

    def test_multiple_documents(self):
        processor = make_processor()
        docs = [FakeDoc(text="Doc 1", score=0.95), FakeDoc(text="Doc 2", score=0.88)]
        result = processor._format_documents(docs)
        assert "1. Doc 1 (score=0.95)" in result
        assert "2. Doc 2 (score=0.88)" in result


class TestGetLatestUserText:
    def test_single_string_content(self):
        messages = [
            {"role": "system", "content": "You are a bot."},
            {"role": "user", "content": "What is the weather?"},
        ]
        assert MossIndexProcessor._get_latest_user_text(messages) == "What is the weather?"

    def test_multimodal_list_content(self):
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this:"},
                    {"type": "image_url", "url": "https://example.com/img.png"},
                ],
            }
        ]
        assert MossIndexProcessor._get_latest_user_text(messages) == "Describe this:"

    def test_no_user_message(self):
        messages = [{"role": "system", "content": "Initial prompt"}]
        assert MossIndexProcessor._get_latest_user_text(messages) is None

    def test_picks_latest_user_message(self):
        messages = [
            {"role": "user", "content": "First message"},
            {"role": "assistant", "content": "Response"},
            {"role": "user", "content": "Second message"},
        ]
        assert MossIndexProcessor._get_latest_user_text(messages) == "Second message"


class TestProcessorPipeline:
    def test_can_generate_metrics(self):
        processor = make_processor()
        assert processor.can_generate_metrics() is True

    @pytest.mark.asyncio
    async def test_retrieve_documents(self):
        processor = make_processor()
        mock_res = MagicMock()
        mock_res.docs = [FakeDoc(text="Doc")]
        mock_res.time_taken_ms = 12.0
        processor._client.query = AsyncMock(return_value=mock_res)

        res = await processor.retrieve_documents("test query")
        assert res == mock_res
        processor._client.query.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_non_context_frame_passes_through(self):
        processor = make_processor()
        processor.push_frame = AsyncMock()

        dummy_frame = Frame()
        await processor.process_frame(dummy_frame, FrameDirection.DOWNSTREAM)
        processor.push_frame.assert_awaited_once_with(dummy_frame, FrameDirection.DOWNSTREAM)

    @pytest.mark.asyncio
    async def test_process_context_frame_injects_documents(self):
        processor = make_processor()
        processor.push_frame = AsyncMock()

        mock_search_result = MagicMock()
        mock_search_result.docs = [FakeDoc(text="Retrieved doc info", score=0.88)]
        mock_search_result.time_taken_ms = 5.0
        processor.retrieve_documents = AsyncMock(return_value=mock_search_result)

        context = LLMContext(
            messages=[
                {"role": "system", "content": "Base prompt"},
                {"role": "user", "content": "Where is the Eiffel Tower?"},
            ]
        )
        frame = LLMContextFrame(context=context)

        await processor.process_frame(frame, FrameDirection.DOWNSTREAM)

        processor.retrieve_documents.assert_awaited_once_with("Where is the Eiffel Tower?")
        messages = context.get_messages()
        assert len(messages) == 3
        assert messages[-1]["role"] == "system"
        assert "Retrieved doc info" in messages[-1]["content"]

    @pytest.mark.asyncio
    async def test_duplicate_query_skips_retrieval(self):
        processor = make_processor()
        processor.push_frame = AsyncMock()
        processor.retrieve_documents = AsyncMock()
        processor._last_query = "Same query"

        context = LLMContext(messages=[{"role": "user", "content": "Same query"}])
        frame = LLMContextFrame(context=context)

        await processor.process_frame(frame, FrameDirection.DOWNSTREAM)
        processor.retrieve_documents.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_process_messages_update_frame(self):
        processor = make_processor()
        processor.push_frame = AsyncMock()

        mock_search_result = MagicMock()
        mock_search_result.docs = [FakeDoc(text="Doc", score=0.9)]
        mock_search_result.time_taken_ms = 4.0
        processor.retrieve_documents = AsyncMock(return_value=mock_search_result)

        messages = [{"role": "user", "content": "Tell me a fact"}]
        frame = LLMMessagesUpdateFrame(messages=messages)

        await processor.process_frame(frame, FrameDirection.DOWNSTREAM)
        processor.push_frame.assert_awaited_once()
        sent_frame = processor.push_frame.call_args[0][0]
        assert isinstance(sent_frame, LLMMessagesUpdateFrame)

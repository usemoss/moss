#
# Copyright (c) 2026, Moss Team
#
# SPDX-License-Identifier: BSD-2-Clause
#

from types import SimpleNamespace

from pipecat.frames.frames import ErrorFrame, LLMContextFrame, LLMMessagesUpdateFrame, TextFrame
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.tests.utils import run_test

from pipecat_moss import MossRetrievalService, QueryOptions
from pipecat_moss.moss_index_processor import MossIndexProcessor


class FakeClient:
    def __init__(self, docs, error=None):
        self.docs = docs
        self.error = error
        self.calls = []

    async def query(self, name, query, options=None):
        self.calls.append((name, query, options))
        if self.error:
            raise self.error
        return SimpleNamespace(docs=self.docs, time_taken_ms=1.5)


def doc(text, **meta):
    return SimpleNamespace(text=text, metadata=meta, score=0.9)


async def test_context_frame_gets_retrieved_docs():
    client = FakeClient([doc("Rex is the dog.", source="memories")])
    processor = MossIndexProcessor(client=client, index_name="memories", top_k=3, alpha=0.5)
    context = LLMContext([{"role": "user", "content": "What's my dog's name?"}])
    frame = LLMContextFrame(context=context)

    down, _ = await run_test(
        processor, frames_to_send=[frame], expected_down_frames=[LLMContextFrame]
    )

    name, query, options = client.calls[0]
    assert (name, query) == ("memories", "What's my dog's name?")
    assert isinstance(options, QueryOptions)
    assert (options.top_k, options.alpha) == (3, 0.5)
    assert down[0] is frame
    added = context.get_messages()[-1]
    assert added["role"] == "system"
    assert "1. Rex is the dog. (source=memories, score=0.9)" in added["content"]


async def test_messages_update_frame_keeps_run_llm_and_gets_docs():
    client = FakeClient([doc("Rex is the dog.")])
    processor = MossIndexProcessor(client=client, index_name="memories")
    frame = LLMMessagesUpdateFrame(
        messages=[{"role": "user", "content": "What's my dog's name?"}], run_llm=True
    )

    down, _ = await run_test(
        processor, frames_to_send=[frame], expected_down_frames=[LLMMessagesUpdateFrame]
    )

    assert down[0] is frame
    assert frame.run_llm is True
    assert frame.messages[-1]["role"] == "system"
    assert "Rex is the dog." in frame.messages[-1]["content"]


async def test_a_failed_retrieval_still_forwards_the_frame():
    client = FakeClient([], error=RuntimeError("index not loaded"))
    processor = MossIndexProcessor(client=client, index_name="memories")
    context = LLMContext([{"role": "user", "content": "hello"}])
    frame = LLMContextFrame(context=context)

    down, up = await run_test(
        processor,
        frames_to_send=[frame],
        expected_down_frames=[LLMContextFrame],
        expected_up_frames=[ErrorFrame],
    )

    assert down[0] is frame
    assert "index not loaded" in up[0].error
    assert context.get_messages() == [{"role": "user", "content": "hello"}]


async def test_duplicate_query_is_not_repeated():
    client = FakeClient([])
    processor = MossIndexProcessor(client=client, index_name="memories")
    context = LLMContext([{"role": "user", "content": "hello"}])

    await run_test(
        processor,
        frames_to_send=[LLMContextFrame(context=context), LLMContextFrame(context=context)],
        expected_down_frames=[LLMContextFrame, LLMContextFrame],
    )

    assert len(client.calls) == 1
    assert context.get_messages() == [{"role": "user", "content": "hello"}]


async def test_other_frames_pass_through():
    client = FakeClient([])
    processor = MossIndexProcessor(client=client, index_name="memories")

    await run_test(processor, frames_to_send=[TextFrame("hi")], expected_down_frames=[TextFrame])

    assert client.calls == []


def test_service_reads_env_credentials(monkeypatch):
    monkeypatch.setenv("MOSS_PROJECT_ID", "pid")
    monkeypatch.setenv("MOSS_PROJECT_KEY", "pkey")
    service = MossRetrievalService()
    processor = service.query("memories", top_k=2)
    assert isinstance(processor, MossIndexProcessor)
    assert processor._top_k == 2


def test_service_requires_credentials(monkeypatch):
    monkeypatch.delenv("MOSS_PROJECT_ID", raising=False)
    monkeypatch.delenv("MOSS_PROJECT_KEY", raising=False)
    try:
        MossRetrievalService()
    except ValueError:
        return
    raise AssertionError("expected ValueError")

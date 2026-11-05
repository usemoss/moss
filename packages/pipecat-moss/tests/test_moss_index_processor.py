#
# Copyright (c) 2026, Moss Team
#
# SPDX-License-Identifier: BSD-2-Clause
#

from dataclasses import dataclass
from types import SimpleNamespace

from pipecat.frames.frames import (
    DataFrame,
    ErrorFrame,
    LLMContextFrame,
    LLMMessagesAppendFrame,
    TextFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.tests.utils import SleepFrame, run_test

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


class AnswersByQuery(FakeClient):
    def __init__(self, answers):
        super().__init__([])
        self.answers = answers

    async def query(self, name, query, options=None):
        self.calls.append((name, query, options))
        answer = self.answers[query]
        if isinstance(answer, Exception):
            raise answer
        return SimpleNamespace(docs=answer, time_taken_ms=1.5)


@dataclass
class SpeculatedTurn(DataFrame):
    text: str


class Speculate(FrameProcessor):
    """Runs a speculated turn over a copy of the context, as pipecat's user aggregator does."""

    def __init__(self, context):
        super().__init__()
        self.context = context

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, SpeculatedTurn):
            turn = {"role": "user", "content": frame.text}
            provisional = LLMContext(messages=[*self.context.get_messages(), turn])
            frame = LLMContextFrame(context=provisional)
            # Pipecat 1.8 frames take no `speculation` argument.
            frame.speculation = True
        await self.push_frame(frame, direction)


def doc(text, **meta):
    return SimpleNamespace(text=text, metadata=meta, score=0.9)


def turns(*exchanges):
    """Frames that reach the user aggregator for each (assistant reply, user question).

    Each turn waits for the last one to pass the processors, which share one context.
    """
    frames = []
    for reply, question in exchanges:
        messages = [{"role": "assistant", "content": reply}] if reply else []
        messages.append({"role": "user", "content": question})
        frames += [LLMMessagesAppendFrame(messages=messages, run_llm=True), SleepFrame(sleep=0.1)]
    return frames


async def run_behind_aggregator(*processors, exchanges):
    context = LLMContext()
    pipeline = Pipeline([LLMContextAggregatorPair(context).user(), *processors])
    down, _ = await run_test(pipeline, frames_to_send=turns(*exchanges))
    assert [type(frame) for frame in down].count(LLMContextFrame) == len(exchanges)
    return [m["content"] for m in context.get_messages() if m["role"] == "system"]


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
    assert isinstance(up[0].exception, RuntimeError)
    assert context.get_messages() == [{"role": "user", "content": "hello"}]


async def test_each_turn_replaces_the_passages_of_the_last_one():
    client = AnswersByQuery(
        {"Who is Rex?": [doc("Rex is the dog.")], "Who is Tom?": [doc("Tom is the cat.")]}
    )
    processor = MossIndexProcessor(client=client, index_name="memories")

    passages = await run_behind_aggregator(
        processor, exchanges=[(None, "Who is Rex?"), ("Rex is your dog.", "Who is Tom?")]
    )

    assert len(passages) == 1
    assert "Tom is the cat." in passages[0]
    assert "Rex is the dog." not in passages[0]


async def test_a_turn_without_passages_drops_the_last_ones():
    client = AnswersByQuery({"Who is Rex?": [doc("Rex is the dog.")], "Hello": []})
    processor = MossIndexProcessor(client=client, index_name="memories")

    passages = await run_behind_aggregator(
        processor, exchanges=[(None, "Who is Rex?"), ("Rex is your dog.", "Hello")]
    )

    assert passages == []


async def test_each_index_keeps_only_its_own_latest_passages():
    pets = MossIndexProcessor(
        client=AnswersByQuery({"Rex?": [doc("Rex is the dog.")], "Tom?": [doc("Tom is the cat.")]}),
        index_name="pets",
    )
    places = MossIndexProcessor(
        client=AnswersByQuery(
            {"Rex?": [doc("Rex lives in Lisbon.")], "Tom?": [doc("Tom lives in Porto.")]}
        ),
        index_name="places",
    )

    passages = await run_behind_aggregator(
        pets, places, exchanges=[(None, "Rex?"), ("Rex is your dog.", "Tom?")]
    )

    assert len(passages) == 2
    assert any("Tom is the cat." in passage for passage in passages)
    assert any("Tom lives in Porto." in passage for passage in passages)
    assert not any("Rex" in passage for passage in passages)


async def test_passages_equal_to_another_index_last_ones_stay():
    pets = MossIndexProcessor(
        client=AnswersByQuery(
            {"Rex?": [doc("Rex is the dog.")], "Tom?": [doc("Tom lives in Porto.")]}
        ),
        index_name="pets",
    )
    places = MossIndexProcessor(
        client=AnswersByQuery(
            {"Rex?": [doc("Tom lives in Porto.")], "Tom?": [doc("Porto is in Portugal.")]}
        ),
        index_name="places",
    )

    passages = await run_behind_aggregator(
        pets, places, exchanges=[(None, "Rex?"), ("Rex is your dog.", "Tom?")]
    )

    assert len(passages) == 2
    assert any("Tom lives in Porto." in passage for passage in passages)
    assert any("Porto is in Portugal." in passage for passage in passages)


async def test_a_speculative_turn_leaves_the_real_context_to_the_next_turn():
    client = AnswersByQuery(
        {
            "Who is Rex?": [doc("Rex is the dog.")],
            "Who is Tom?": [doc("Tom is the cat.")],
            "Who is Ana?": [doc("Ana is the vet.")],
        }
    )
    processor = MossIndexProcessor(client=client, index_name="memories")
    context = LLMContext()
    pipeline = Pipeline([LLMContextAggregatorPair(context).user(), Speculate(context), processor])
    confirmed = {"role": "user", "content": "Who is Tom?"}
    next_turn = [
        {"role": "assistant", "content": "Tom is your cat."},
        {"role": "user", "content": "Who is Ana?"},
    ]

    down, _ = await run_test(
        pipeline,
        frames_to_send=[
            *turns((None, "Who is Rex?")),
            SpeculatedTurn(text="Who is Tom?"),
            SleepFrame(sleep=0.1),
            # A confirmed speculation is written without a second inference.
            LLMMessagesAppendFrame(messages=[confirmed], run_llm=False),
            SleepFrame(sleep=0.1),
            LLMMessagesAppendFrame(messages=next_turn, run_llm=True),
            SleepFrame(sleep=0.1),
        ],
    )

    speculation = next(
        f for f in down if isinstance(f, LLMContextFrame) and getattr(f, "speculation", False)
    )
    speculated = [m["content"] for m in speculation.context.get_messages() if m["role"] == "system"]
    assert len(speculated) == 1
    assert "Tom is the cat." in speculated[0]
    passages = [m["content"] for m in context.get_messages() if m["role"] == "system"]
    assert len(passages) == 1
    assert "Ana is the vet." in passages[0]


async def test_a_failed_query_drops_the_last_passages():
    client = AnswersByQuery(
        {"Who is Rex?": [doc("Rex is the dog.")], "Who is Tom?": RuntimeError("index not loaded")}
    )
    processor = MossIndexProcessor(client=client, index_name="memories")

    passages = await run_behind_aggregator(
        processor, exchanges=[(None, "Who is Rex?"), ("Rex is your dog.", "Who is Tom?")]
    )

    assert passages == []


async def test_asking_again_after_a_failed_query_retrieves_again():
    client = AnswersByQuery(
        {"Who is Rex?": [doc("Rex is the dog.")], "Who is Tom?": RuntimeError("index not loaded")}
    )
    processor = MossIndexProcessor(client=client, index_name="memories")

    passages = await run_behind_aggregator(
        processor,
        exchanges=[
            (None, "Who is Rex?"),
            ("Rex is your dog.", "Who is Tom?"),
            ("Sorry.", "Who is Rex?"),
        ],
    )

    assert len(passages) == 1
    assert "Rex is the dog." in passages[0]


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

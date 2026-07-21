#
# SPDX-License-Identifier: BSD-2-Clause
#
"""Moss voice-agent speed showcase (Pipecat).

A real-time voice customer-support agent that grounds every reply in a Moss
index. It prints the per-turn retrieval latency so you can see Moss's
sub-10ms lookups live, and a SIMULATE_REMOTE_MS toggle lets you demo the same
agent with a remote vector DB's latency instead — so the speed difference is
audible.

Services: Deepgram (STT), OpenAI (LLM), ElevenLabs (TTS), Moss (retrieval).

Run:
    uv sync
    cp .env.example .env        # add your keys
    python create_index.py      # build the demo index (once)
    python bot.py               # open the printed URL and talk

Demo the difference:
    SIMULATE_REMOTE_MS=0   python bot.py   # Moss: snappy (~2 ms retrieval)
    SIMULATE_REMOTE_MS=400 python bot.py   # remote DB: audible lag per turn
"""

import os

from dotenv import load_dotenv
from loguru import logger
from moss import MossClient
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import LLMMessagesAppendFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.processors.frameworks.rtvi import RTVIObserver, RTVIObserverParams, RTVIProcessor
from pipecat.runner.run import main as runner_main
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.base_transport import BaseTransport, TransportParams

from moss_speed_retrieval import MossSpeedRetrieval

load_dotenv(override=True)

SIMULATE_REMOTE_MS = int(os.getenv("SIMULATE_REMOTE_MS", "0"))
_MODE = f"REMOTE-SIM (+{SIMULATE_REMOTE_MS} ms/turn)" if SIMULATE_REMOTE_MS else "MOSS (in-process, ~2 ms/turn)"


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):
    """Wire up STT -> Moss retrieval -> LLM -> TTS and run the pipeline."""
    stt = DeepgramSTTService(api_key=os.environ["DEEPGRAM_API_KEY"])
    tts = ElevenLabsTTSService(
        api_key=os.environ["ELEVENLABS_TTS_KEY"],
        voice_id=os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB"),
    )
    llm = OpenAILLMService(
        api_key=os.environ["OPENAI_API_KEY"],
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    )

    index_name = os.environ["MOSS_INDEX_NAME"]
    client = MossClient(os.environ["MOSS_PROJECT_ID"], os.environ["MOSS_PROJECT_KEY"])
    await client.load_index(index_name)
    logger.info(f"Moss index '{index_name}' loaded locally · retrieval mode: {_MODE}")

    moss = MossSpeedRetrieval(
        client,
        index_name,
        top_k=int(os.getenv("MOSS_TOP_K", "5")),
        alpha=float(os.getenv("MOSS_ALPHA", "0.8")),
        simulate_remote_ms=SIMULATE_REMOTE_MS,
    )

    system_content = (
        "You are a friendly, concise customer-support voice assistant for an online store. "
        "Answer questions about orders, shipping, returns, and payments. Keep replies short and "
        "conversational. Use the provided knowledge-base passages to answer accurately; if they "
        "don't cover the question, say so briefly."
    )
    messages = [{"role": "system", "content": system_content}]
    context = LLMContext(messages)
    context_aggregator = LLMContextAggregatorPair(context)
    rtvi = RTVIProcessor()

    pipeline = Pipeline(
        [
            transport.input(),
            rtvi,
            stt,
            context_aggregator.user(),
            moss,  # inject Moss knowledge (+ report retrieval latency)
            llm,
            tts,
            transport.output(),
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            enable_metrics=True, enable_usage_metrics=True, report_only_initial_ttfb=True
        ),
        observers=[RTVIObserver(rtvi, params=RTVIObserverParams())],
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info(f"Caller connected · retrieval mode: {_MODE}")
        await task.queue_frames(
            [
                LLMMessagesAppendFrame(
                    messages=[
                        {
                            "role": "system",
                            "content": "The caller just connected. Greet them warmly and ask how you can help.",
                        }
                    ],
                    run_llm=True,
                )
            ]
        )

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Caller disconnected")
        await task.cancel()

    runner = PipelineRunner(handle_sigint=runner_args.handle_sigint)
    await runner.run(task)


async def bot(runner_args: RunnerArguments):
    """Entry point: validate env, create the transport, run."""
    required = ["DEEPGRAM_API_KEY", "OPENAI_API_KEY", "ELEVENLABS_TTS_KEY",
                "MOSS_PROJECT_ID", "MOSS_PROJECT_KEY", "MOSS_INDEX_NAME"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        logger.error(f"Missing env vars: {', '.join(missing)} — see .env.example")
        return

    print(f"\n=== Moss voice-agent speed showcase — retrieval mode: {_MODE} ===")
    print("Open the URL below, click Connect, and talk. Watch the log for per-turn retrieval latency.\n")

    transport_params = {
        "webrtc": lambda: TransportParams(
            audio_in_enabled=True, audio_out_enabled=True, vad_analyzer=SileroVADAnalyzer()
        ),
    }
    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args)


if __name__ == "__main__":
    runner_main()

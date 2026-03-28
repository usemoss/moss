#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Pipecat Voice AI Bot with Ollama (local LLM) + Moss Semantic Retrieval + Hume AI TTS.

A voice AI assistant that runs LLM inference locally via Ollama:
- Uses Ollama for local LLM inference (no OpenAI API key needed)
- Searches knowledge base using Moss semantic retrieval
- Uses Hume AI (Octave) for expressive text-to-speech
- Supports real-time voice conversations
- Follows official Pipecat quickstart pattern

Required services:
- Ollama (local LLM, runs in Docker or standalone)
- Moss (Semantic Retrieval)
- Deepgram (Speech-to-Text)
- Hume AI (Text-to-Speech)

Run with Docker::

    docker compose up

Or run locally::

    uv run hume_ollama_bot.py
"""

import os

from dotenv import load_dotenv
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer, VADParams
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.frameworks.rtvi import RTVIConfig, RTVIObserver, RTVIProcessor
from pipecat.runner.run import main as runner_main
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.hume.tts import HumeTTSService
from pipecat.services.ollama.llm import OLLamaLLMService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.daily.transport import DailyParams
from pipecat_moss import MossRetrievalService
from pipecat_moss.moss_index_processor import MossIndexProcessor

# Load environment variables from .env file
load_dotenv(override=True)

print("Starting Ollama + Hume AI Voice Bot...")
logger.debug("All components loaded successfully!")

async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):
    """Run the voice bot pipeline with Ollama LLM and Hume AI TTS."""

    # Initialize stt, tts, llm services
    logger.debug("Starting Ollama + Hume AI voice bot")
    dg_api_key = os.getenv("DEEPGRAM_API_KEY")
    hume_api_key = os.getenv("HUME_API_KEY")

    assert dg_api_key is not None
    assert hume_api_key is not None

    stt = DeepgramSTTService(api_key=dg_api_key)
    tts = HumeTTSService(
        api_key=hume_api_key,
        voice_id="5bbc32c1-a1f6-44e8-bedb-9870f23619e2",
    )
    llm = OLLamaLLMService(
        model=os.getenv("OLLAMA_MODEL", "llama3.2"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://ollama:11434/v1"),
    )

    # Configure Moss retrieval credentials and settings
    project_id = os.getenv("MOSS_PROJECT_ID")
    project_key = os.getenv("MOSS_PROJECT_KEY")
    index_name = os.getenv("MOSS_INDEX_NAME")

    assert project_id is not None
    assert project_key is not None
    assert index_name is not None

    top_k = int(os.getenv("MOSS_TOP_K", "5"))

    moss_service = MossRetrievalService(
        project_id=project_id,
        project_key=project_key,
        system_prompt="Relevant passages from the Moss knowledge base:\n\n",
    )

    # Patch MossIndexProcessor to use 'user' role instead of 'system'
    # Ollama ignores system messages that follow user messages
    _orig_process = MossIndexProcessor.process_frame

    async def _patched_process(self, frame, direction):
        from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContextFrame
        if isinstance(frame, OpenAILLMContextFrame):
            context = frame.context
            msgs_before = len(context.get_messages())
            await _orig_process(self, frame, direction)
            msgs_after = context.get_messages()
            # Convert any new system messages added by Moss to user role
            for i in range(msgs_before, len(msgs_after)):
                if msgs_after[i].get("role") == "system" and "Moss knowledge base" in msgs_after[i].get("content", ""):
                    msgs_after[i]["role"] = "user"
        else:
            await _orig_process(self, frame, direction)

    MossIndexProcessor.process_frame = _patched_process

    # Load the Moss index
    await moss_service.load_index(index_name)
    logger.debug(f"Moss retrieval service initialized (index: {index_name})")

    # System prompt with semantic retrieval support
    system_content = """You are a concise voice assistant for Moss — a semantic search and retrieval platform that lets developers add instant, relevant search to any app.

Rules:
- Answer in 1–2 short sentences. No filler, no preamble.
- Always ground answers in the provided knowledge base passages.
- If passages contain the answer, state it directly. If not, say "I don't have that info" and suggest where to look.
- Use plain language — this is voice, not text. Avoid bullet points, code blocks, or markdown.
- When explaining Moss concepts, lead with what it does, then how."""

    # Initialize conversation context and pipeline components
    messages = [
        {
            "role": "system",
            "content": system_content,
        },
    ]

    context = OpenAILLMContext(messages)  # type: ignore
    context_aggregator = llm.create_context_aggregator(context)
    rtvi = RTVIProcessor(config=RTVIConfig(config=[]))

    # Build the processing pipeline with Moss information injection
    pipeline = Pipeline(
        [
            transport.input(),  # Transport user input
            rtvi,  # RTVI processor
            stt,  # Speech-to-text
            context_aggregator.user(),  # User responses
            moss_service.query(index_name, top_k=top_k),  # Moss retrieval
            llm,  # LLM (receives enhanced context)
            tts,  # Text-to-speech
            transport.output(),  # Transport bot output
            context_aggregator.assistant(),  # Assistant spoken responses
        ]
    )

    # Create and configure the pipeline task
    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
            report_only_initial_ttfb=True,
        ),
        observers=[RTVIObserver(rtvi)],
    )

    # Define transport event handlers
    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.debug("Customer connected to support")
        # Kick off the conversation with a customer support greeting
        greeting = (
            "A customer has just connected to customer support. Greet them warmly and ask how you "
            "can help them today."
        )
        messages.append({"role": "user", "content": greeting})
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.debug("Customer disconnected from support")
        await task.cancel()

    runner = PipelineRunner(handle_sigint=runner_args.handle_sigint)

    await runner.run(task)

# Runner entry point
async def bot(runner_args: RunnerArguments):
    """Main bot entry point for the Ollama + Hume AI voice bot."""
    # Check required environment variables
    required_vars = [
        "DEEPGRAM_API_KEY",
        "HUME_API_KEY",
        "MOSS_PROJECT_ID",
        "MOSS_PROJECT_KEY",
        "MOSS_INDEX_NAME",
    ]

    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error("Missing required environment variables:")
        for var in missing_vars:
            logger.error(f"   - {var}")
        logger.error("\nPlease update your .env file with the required API keys")
        logger.error("Get your Moss credentials from: https://portal.usemoss.dev")
        logger.error("Get your Hume AI key from: https://platform.hume.ai")
        logger.error("Ollama runs locally — no API key needed")
        return

    transport_params = {
        "daily": lambda: DailyParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=SileroVADAnalyzer(params=VADParams(threshold=0.7, min_volume=0.5)),
        ),
        "webrtc": lambda: TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=SileroVADAnalyzer(params=VADParams(threshold=0.7, min_volume=0.5)),
        ),
    }

    transport = await create_transport(runner_args, transport_params)

    await run_bot(transport, runner_args)


if __name__ == "__main__":
    runner_main()

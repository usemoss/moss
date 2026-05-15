"""Voice agent demo: Google ADK Live (BIDI) + Moss.

A CLI voice agent. Speak into your microphone; the agent calls `moss_search`
when it needs to look something up, and replies back as audio.

Requires::

    pip install google-adk moss python-dotenv sounddevice

On macOS you may also need portaudio::

    brew install portaudio

Run::

    python voice_demo.py

Press Ctrl+C to exit.
"""

import asyncio
import os
import queue
import sys
import time

import sounddevice as sd
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.agents.live_request_queue import LiveRequestQueue
from google.adk.agents.run_config import (
    RunConfig,
    StreamingMode,
    ToolThreadPoolConfig,
)
from google.adk.runners import InMemoryRunner
from google.genai import types
from moss import DocumentInfo, MossClient

from moss_agent.moss_search import make_moss_search

APP_NAME = "moss_adk_voice_demo"
USER_ID = "voice_user"

# Half-cascade Gemini Live model: audio in / audio out, with stable tool support.
VOICE_MODEL = os.getenv("ADK_MODEL", "gemini-3.1-flash-live-preview")

# Gemini Live API audio formats.
INPUT_SAMPLE_RATE = 16000   # 16 kHz mono PCM int16 going up
OUTPUT_SAMPLE_RATE = 24000  # 24 kHz mono PCM int16 coming back
INPUT_CHUNK_MS = 100        # send mic chunks every 100 ms
# Extra tail (seconds) to keep the mic muted after the speaker finishes,
# so reverb/room decay doesn't get re-transcribed.
ECHO_TAIL_SECONDS = 0.4


class MicGate:
    """Half-duplex gate: mute the mic while the model is speaking.

    Without this, speaker output is picked up by the mic, transcribed as
    user input, and the model ends up replying to its own echo in a loop.
    Use headphones to keep barge-in instead.
    """

    def __init__(self) -> None:
        self._muted_until = 0.0

    def extend(self, audio_bytes: bytes, sample_rate: int) -> None:
        duration = len(audio_bytes) / 2 / sample_rate  # int16 mono
        end = time.monotonic() + duration + ECHO_TAIL_SECONDS
        if end > self._muted_until:
            self._muted_until = end

    def is_muted(self) -> bool:
        return time.monotonic() < self._muted_until

SEED_DOCS = [
    DocumentInfo(id="1", text="Refunds are processed within 3-5 business days of the request."),
    DocumentInfo(id="2", text="You can track your order in the dashboard under 'My Orders'."),
    DocumentInfo(id="3", text="We offer 24/7 live chat support through the help widget."),
    DocumentInfo(id="4", text="Free shipping on orders over $50 in the contiguous US."),
    DocumentInfo(id="5", text="Returns are accepted within 30 days of purchase with original packaging."),
]


async def seed_index_if_needed(client: MossClient, index_name: str) -> None:
    try:
        await client.load_index(index_name)
        print(f"Index '{index_name}' already exists; skipping seed.")
    except Exception:
        print(f"Creating index '{index_name}' with {len(SEED_DOCS)} docs...")
        await client.create_index(index_name, SEED_DOCS)
        await client.load_index(index_name)


async def microphone_to_queue(
    live_request_queue: LiveRequestQueue,
    loop: asyncio.AbstractEventLoop,
    mic_gate: MicGate,
) -> None:
    """Capture mic and forward 16 kHz PCM chunks into the ADK live queue."""
    chunk_frames = int(INPUT_SAMPLE_RATE * INPUT_CHUNK_MS / 1000)
    mic_q: queue.Queue[bytes] = queue.Queue()

    def callback(indata, frames, time_info, status):
        if status:
            print(f"[mic] {status}", file=sys.stderr)
        # indata is int16 numpy array; send raw bytes.
        mic_q.put(bytes(indata))

    with sd.RawInputStream(
        samplerate=INPUT_SAMPLE_RATE,
        blocksize=chunk_frames,
        dtype="int16",
        channels=1,
        callback=callback,
    ):
        print("[mic] open - start talking. Ctrl+C to exit.")
        while True:
            chunk = await loop.run_in_executor(None, mic_q.get)
            if mic_gate.is_muted():
                continue
            live_request_queue.send_realtime(
                types.Blob(mime_type=f"audio/pcm;rate={INPUT_SAMPLE_RATE}", data=chunk)
            )


async def play_agent_events(
    runner: InMemoryRunner,
    session_id: str,
    live_request_queue: LiveRequestQueue,
    mic_gate: MicGate,
) -> None:
    """Consume run_live() events: play audio out, log tool calls and transcripts."""
    run_config = RunConfig(
        streaming_mode=StreamingMode.BIDI,
        response_modalities=["AUDIO"],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        # Reconnect to a dropped Live session instead of losing it.
        session_resumption=types.SessionResumptionConfig(),
        # Run blocking tool calls off the event loop so audio stays responsive.
        tool_thread_pool_config=ToolThreadPoolConfig(),
    )

    speaker = sd.RawOutputStream(
        samplerate=OUTPUT_SAMPLE_RATE,
        dtype="int16",
        channels=1,
    )
    speaker.start()

    try:
        async for event in runner.run_live(
            user_id=USER_ID,
            session_id=session_id,
            live_request_queue=live_request_queue,
            run_config=run_config,
        ):
            # Live API streams ASR for both sides as separate event fields.
            if event.input_transcription and event.input_transcription.text:
                tag = "user" if event.input_transcription.finished else "user.."
                print(f"[{tag}] {event.input_transcription.text}")
            if event.output_transcription and event.output_transcription.text:
                tag = "model" if event.output_transcription.finished else "model.."
                print(f"[{tag}] {event.output_transcription.text}")

            if not event.content or not event.content.parts:
                continue
            for part in event.content.parts:
                if (
                    part.inline_data
                    and part.inline_data.mime_type
                    and part.inline_data.mime_type.startswith("audio/")
                    and part.inline_data.data
                ):
                    speaker.write(part.inline_data.data)
                    mic_gate.extend(part.inline_data.data, OUTPUT_SAMPLE_RATE)
                if part.text and not getattr(part, "thought", False):
                    print(f"[model-text] {part.text}")
                if part.function_call:
                    print(
                        f"[tool] {part.function_call.name}"
                        f"({part.function_call.args})"
                    )
                if part.function_response:
                    response = part.function_response.response or {}
                    result = response.get("result") if isinstance(response, dict) else response
                    if isinstance(result, str) and len(result) > 300:
                        result = result[:300] + "..."
                    print(f"[tool-result] {part.function_response.name} -> {result}")
    finally:
        speaker.stop()
        speaker.close()


async def main() -> None:
    load_dotenv()

    if not os.getenv("MOSS_PROJECT_ID") or not os.getenv("MOSS_PROJECT_KEY"):
        sys.exit("Set MOSS_PROJECT_ID and MOSS_PROJECT_KEY in .env first.")
    if not os.getenv("GOOGLE_API_KEY"):
        sys.exit(
            "Set GOOGLE_API_KEY in .env "
            "(https://aistudio.google.com/app/apikey)."
        )

    index_name = os.getenv("MOSS_INDEX_NAME", "moss-adk-demo-index")

    seed_client = MossClient(
        project_id=os.getenv("MOSS_PROJECT_ID"),
        project_key=os.getenv("MOSS_PROJECT_KEY"),
    )
    await seed_index_if_needed(seed_client, index_name)

    load_index, moss_search = make_moss_search(index_name=index_name)
    await load_index()

    agent = Agent(
        name="moss_voice_agent",
        model=VOICE_MODEL,
        description="Voice customer support agent backed by Moss.",
        instruction=(
            "You are a friendly support assistant on a voice call. "
            "Before answering questions about orders, refunds, shipping, "
            "or support, call the `moss_search` tool with the user's "
            "question. Keep answers short and conversational."
        ),
        tools=[moss_search],
    )

    runner = InMemoryRunner(agent=agent, app_name=APP_NAME)
    session = await runner.session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID
    )

    live_request_queue = LiveRequestQueue()
    loop = asyncio.get_running_loop()
    mic_gate = MicGate()

    print(f"\nVoice agent ready (model={VOICE_MODEL}).")
    print("Speak: 'How long do refunds take?' or 'What's your return policy?'\n")

    try:
        await asyncio.gather(
            microphone_to_queue(live_request_queue, loop, mic_gate),
            play_agent_events(runner, session.id, live_request_queue, mic_gate),
        )
    except KeyboardInterrupt:
        print("\n[exit] bye.")
    finally:
        live_request_queue.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

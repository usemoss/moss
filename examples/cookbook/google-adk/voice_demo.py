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

import sounddevice as sd
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.agents.live_request_queue import LiveRequestQueue
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import InMemoryRunner
from google.genai import types
from moss import DocumentInfo, MossClient

from moss_adk import MossSearchTool

APP_NAME = "moss_adk_voice_demo"
USER_ID = "voice_user"

# Native-audio Gemini Live model: takes audio in, returns audio out.
VOICE_MODEL = os.getenv(
    "ADK_VOICE_MODEL", "gemini-2.5-flash-native-audio-preview-12-2025"
)

# Gemini Live API audio formats.
INPUT_SAMPLE_RATE = 16000   # 16 kHz mono PCM int16 going up
OUTPUT_SAMPLE_RATE = 24000  # 24 kHz mono PCM int16 coming back
INPUT_CHUNK_MS = 100        # send mic chunks every 100 ms

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
    live_request_queue: LiveRequestQueue, loop: asyncio.AbstractEventLoop
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
        print("[mic] open — start talking. Ctrl+C to exit.")
        while True:
            chunk = await loop.run_in_executor(None, mic_q.get)
            live_request_queue.send_realtime(
                types.Blob(mime_type=f"audio/pcm;rate={INPUT_SAMPLE_RATE}", data=chunk)
            )


async def play_agent_events(
    runner: InMemoryRunner, session_id: str, live_request_queue: LiveRequestQueue
) -> None:
    """Consume run_live() events: play audio out, log tool calls and transcripts."""
    run_config = RunConfig(
        streaming_mode=StreamingMode.BIDI,
        response_modalities=["AUDIO"],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
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
            if not event.content or not event.content.parts:
                continue
            for part in event.content.parts:
                # Audio reply: play it.
                if (
                    part.inline_data
                    and part.inline_data.mime_type
                    and part.inline_data.mime_type.startswith("audio/")
                    and part.inline_data.data
                ):
                    speaker.write(part.inline_data.data)
                # Transcripts and tool calls: log for visibility.
                if part.text:
                    print(f"[{event.author}] {part.text}")
                if part.function_call:
                    print(
                        f"[tool] {part.function_call.name}"
                        f"({part.function_call.args})"
                    )
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

    moss = MossSearchTool(index_name=index_name)

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
        tools=[moss.search_tool],
    )

    runner = InMemoryRunner(agent=agent, app_name=APP_NAME)
    session = await runner.session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID
    )

    live_request_queue = LiveRequestQueue()
    loop = asyncio.get_running_loop()

    print(f"\nVoice agent ready (model={VOICE_MODEL}).")
    print("Speak: 'How long do refunds take?' or 'What's your return policy?'\n")

    try:
        await asyncio.gather(
            microphone_to_queue(live_request_queue, loop),
            play_agent_events(runner, session.id, live_request_queue),
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

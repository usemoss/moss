"""
bot.py - Bharat Benefits Voice Agent
============================================
Continuous voice loop:

    mic -> Sarvam STT -> Moss RAG -> Sarvam LLM -> Sarvam TTS -> speaker
           (repeats until you say "exit" or press Ctrl+C)

Two recording modes:
  - Fixed window (default): records for a set number of seconds per turn.
  - VAD mode (--vad): detects silence automatically so you don't need
    to worry about a timer. Stops recording when you stop speaking.

Usage:
    python bot.py                  # fixed 5s window
    python bot.py --seconds 8      # fixed 8s window
    python bot.py --vad            # voice activity detection (natural pauses)
    python bot.py --text-mode      # type instead of speak (debug)

Environment (.env):
    SARVAM_API_KEY     - Sarvam subscription key
    MOSS_PROJECT_ID    - Moss project ID
    MOSS_PROJECT_KEY   - Moss project key
    MOSS_INDEX_NAME    - default: bharat-benefits
    SARVAM_STT_MODEL   - default: saaras:v3
    SARVAM_CHAT_MODEL  - default: sarvam-105b
    SARVAM_TTS_MODEL   - default: bulbul:v3
    SARVAM_TTS_SPEAKER - default: priya

Install:
    pip install moss httpx python-dotenv sounddevice soundfile numpy simpleaudio webrtcvad
    (webrtcvad is only needed for --vad mode)
"""

import argparse
import asyncio
import base64
import collections
import os
import re
import struct
import sys
import tempfile
import time
from pathlib import Path

import httpx
import numpy as np
import sounddevice as sd
import soundfile as sf
from dotenv import load_dotenv

# -- Config -------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=SCRIPT_DIR / ".env")

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
STT_MODEL = os.getenv("SARVAM_STT_MODEL", "saaras:v3")
CHAT_MODEL = os.getenv("SARVAM_CHAT_MODEL", "sarvam-105b")
TTS_MODEL = os.getenv("SARVAM_TTS_MODEL", "bulbul:v3")
TTS_SPEAKER = os.getenv("SARVAM_TTS_SPEAKER", "priya")

MOSS_PROJECT_ID = os.getenv("MOSS_PROJECT_ID", "")
MOSS_PROJECT_KEY = os.getenv("MOSS_PROJECT_KEY", "")
MOSS_INDEX_NAME = os.getenv("MOSS_INDEX_NAME", "bharat-benefits")

SARVAM_BASE = "https://api.sarvam.ai"
SAMPLE_RATE = 16_000  # Hz - required by Sarvam STT
TOP_K = 3
MAX_TTS_CHARS = 1500

# VAD settings
VAD_FRAME_MS = 30  # ms per frame (webrtcvad supports 10, 20, 30)
VAD_AGGRESSIVENESS = 2  # 0 (least aggressive) to 3 (most aggressive)
VAD_SILENCE_TIMEOUT = 1.2  # seconds of silence before stopping recording
VAD_MAX_SECONDS = 15  # hard cap to prevent runaway recording

EXIT_PHRASES = {
    "exit",
    "quit",
    "stop",
    "bye",
    "goodbye",
    "band karo",
    "band kar",
    "बंद करो",
}

SYSTEM_PROMPT = """You are a voice assistant that answers questions about Indian
government welfare schemes using only the retrieved context provided.

Rules:
- Answer only from the retrieved context. Do not invent eligibility rules, amounts, or deadlines.
- If the context is insufficient, say so and direct the user to the official government portal.
- Keep answers short and suitable for listening - no bullet points, no tables, no markdown.
- 3 to 5 sentences maximum.
- Mention the helpline number if one is present in the context.
- End with: "Please verify the details on the official government portal." """


# -- Helpers ------------------------------------------------------------------


def _key_headers() -> dict:
    return {"api-subscription-key": SARVAM_API_KEY}


def _bearer_headers() -> dict:
    return {
        "Authorization": f"Bearer {SARVAM_API_KEY}",
        "Content-Type": "application/json",
    }


def _check_env():
    missing = [
        v
        for v in ["SARVAM_API_KEY", "MOSS_PROJECT_ID", "MOSS_PROJECT_KEY"]
        if not os.getenv(v)
    ]
    if missing:
        print(
            f"ERROR: missing environment variables: {', '.join(missing)}",
            file=sys.stderr,
        )
        print("Set them in your .env file and try again.", file=sys.stderr)
        sys.exit(1)


# -- Recording: fixed window --------------------------------------------------


def record_fixed(seconds: int = 5) -> Path:
    """Record a fixed number of seconds from the microphone."""
    print(f"\nListening ({seconds}s) ...")
    try:
        audio = sd.rec(
            int(seconds * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
        )
        sd.wait()
    except Exception as e:
        print(f"ERROR: microphone unavailable: {e}", file=sys.stderr)
        sys.exit(1)

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    sf.write(tmp.name, audio, SAMPLE_RATE, subtype="PCM_16")
    tmp.close()
    return Path(tmp.name)


# -- Recording: VAD (voice activity detection) --------------------------------


def record_vad() -> Path:
    """
    Record until the speaker stops talking.
    Uses webrtcvad to detect speech vs silence.
    Stops after VAD_SILENCE_TIMEOUT seconds of continuous silence,
    or VAD_MAX_SECONDS hard cap.

    Requires: pip install webrtcvad
    """
    try:
        import webrtcvad
    except ImportError:
        print(
            "ERROR: webrtcvad not installed. Run: pip install webrtcvad",
            file=sys.stderr,
        )
        print("Or use fixed-window mode (remove --vad flag).", file=sys.stderr)
        sys.exit(1)

    vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)

    frame_samples = int(SAMPLE_RATE * VAD_FRAME_MS / 1000)  # samples per frame
    frame_bytes = frame_samples * 2  # 2 bytes per int16 sample
    silence_frames = int(VAD_SILENCE_TIMEOUT * 1000 / VAD_FRAME_MS)
    max_frames = int(VAD_MAX_SECONDS * 1000 / VAD_FRAME_MS)

    # Ring buffer to keep recent speech even during leading silence
    ring = collections.deque(maxlen=silence_frames)
    frames_recorded = []
    triggered = False
    silent_count = 0

    print("\nListening (speak now, will stop when you pause) ...")

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=frame_samples
    ) as stream:
        total = 0
        while total < max_frames:
            raw, _ = stream.read(frame_samples)
            frame = bytes(raw)
            if len(frame) < frame_bytes:
                continue

            is_speech = vad.is_speech(frame, SAMPLE_RATE)
            total += 1

            if not triggered:
                ring.append((frame, is_speech))
                num_voiced = sum(1 for _, s in ring if s)
                # Start recording if >50% of ring buffer is speech
                if num_voiced > 0.5 * ring.maxlen:
                    triggered = True
                    frames_recorded.extend(f for f, _ in ring)
                    ring.clear()
                    silent_count = 0
            else:
                frames_recorded.append(frame)
                if is_speech:
                    silent_count = 0
                else:
                    silent_count += 1
                    if silent_count > silence_frames:
                        break

    if not frames_recorded:
        return None

    audio_bytes = b"".join(frames_recorded)
    audio_array = np.frombuffer(audio_bytes, dtype=np.int16)

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    sf.write(tmp.name, audio_array, SAMPLE_RATE, subtype="PCM_16")
    tmp.close()
    return Path(tmp.name)


# -- Speech to text (Sarvam STT) ----------------------------------------------


def transcribe(audio_path: Path) -> str:
    """Send audio file to Sarvam STT. Returns transcript string."""
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    resp = httpx.post(
        f"{SARVAM_BASE}/speech-to-text",
        headers=_key_headers(),
        files={"file": (audio_path.name, audio_bytes, "audio/wav")},
        data={"model": STT_MODEL, "language_code": "unknown"},
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()
    transcript = data.get("transcript", "").strip()
    lang = data.get("language_code", "unknown")
    print(f"   heard [{lang}]: {transcript}")

    try:
        audio_path.unlink()
    except Exception:
        pass

    return transcript


# -- Moss RAG retrieval -------------------------------------------------------


async def retrieve(question: str, moss_client) -> str:
    """Query Moss index for relevant scheme context."""
    try:
        from moss import QueryOptions
    except ImportError:
        print("ERROR: moss not installed. Run: pip install moss", file=sys.stderr)
        sys.exit(1)

    print("   searching ...")
    results = await moss_client.query(
        MOSS_INDEX_NAME,
        question,
        QueryOptions(top_k=TOP_K, alpha=0.75),
    )
    if not results.docs:
        return "No relevant information found in the knowledge base."

    parts = []
    for doc in results.docs:
        source = (doc.metadata or {}).get("source", doc.id)
        parts.append(f"[Source: {source}]\n{doc.text}")
    return "\n\n---\n\n".join(parts)


# -- Generate answer (Sarvam Chat) --------------------------------------------


def generate_answer(question: str, context: str, history: list) -> str:
    """Generate a voice-friendly answer using conversation history."""
    user_msg = (
        f"User question: {question}\n\n"
        f"Retrieved context:\n{context}\n\n"
        "Give a short, voice-friendly answer in 3 to 5 sentences."
    )

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history[-6:])  # last 3 turns (6 messages)
    messages.append({"role": "user", "content": user_msg})

    print("   generating answer ...")
    resp = httpx.post(
        f"{SARVAM_BASE}/v1/chat/completions",
        headers=_bearer_headers(),
        json={
            "model": CHAT_MODEL,
            "messages": messages,
            "max_tokens": 300,
            "temperature": 0.2,
        },
        timeout=60.0,
    )
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"].strip()
    answer = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    preview = answer[:120] + ("..." if len(answer) > 120 else "")
    print(f"   answer: {preview}")
    return answer


# -- Text to speech (Sarvam TTS) ----------------------------------------------


def speak(answer: str) -> None:
    """Convert text to speech and play it immediately."""
    text = answer[:MAX_TTS_CHARS]
    print("   speaking ...")

    resp = httpx.post(
        f"{SARVAM_BASE}/text-to-speech",
        headers={**_key_headers(), "Content-Type": "application/json"},
        json={
            "text": text,
            "target_language_code": "en-IN",
            "speaker": TTS_SPEAKER,
            "model": TTS_MODEL,
            "enable_preprocessing": True,
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    audios = resp.json().get("audios", [])
    if not audios:
        print("   WARNING: TTS returned no audio.")
        return

    wav_bytes = base64.b64decode(audios[0])

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.write(wav_bytes)
    tmp.close()

    try:
        import simpleaudio as sa

        wave_obj = sa.WaveObject.from_wave_file(tmp.name)
        play_obj = wave_obj.play()
        play_obj.wait_done()
    except ImportError:
        data, sr = sf.read(tmp.name, dtype="int16")
        sd.play(data, sr)
        sd.wait()
    except Exception as e:
        print(f"   WARNING: playback failed: {e}")
        return

    try:
        Path(tmp.name).unlink()
    except Exception:
        pass


# -- Main loop ----------------------------------------------------------------


async def live_loop(
    record_seconds: int = 5, use_vad: bool = False, text_mode: bool = False
):
    """Continuous voice-to-voice conversation loop."""
    try:
        from moss import MossClient
    except ImportError:
        print("ERROR: moss not installed. Run: pip install moss", file=sys.stderr)
        sys.exit(1)

    _check_env()

    print("\nLoading knowledge base ...")
    moss_client = MossClient(MOSS_PROJECT_ID, MOSS_PROJECT_KEY)
    try:
        await moss_client.load_index(MOSS_INDEX_NAME)
        print(f"Ready: {MOSS_INDEX_NAME}\n")
    except Exception as e:
        print(f"ERROR: could not load index '{MOSS_INDEX_NAME}': {e}", file=sys.stderr)
        print("Run create_index.py first.", file=sys.stderr)
        sys.exit(1)

    conversation_history = []
    turn = 0

    mode_label = "vad" if use_vad else f"{record_seconds}s fixed"
    if text_mode:
        mode_label = "text"

    print("-" * 40)
    print("  Bharat Benefits - Voice Agent")
    print(f"  mode: {mode_label}")
    print("  say 'exit' or press Ctrl+C to stop.")
    print("-" * 40)

    while True:
        turn += 1
        print(f"\n[turn {turn}]")

        try:
            # -- Input --------------------------------------------------------
            if text_mode:
                try:
                    question = input("  question: ").strip()
                except (KeyboardInterrupt, EOFError):
                    break
            elif use_vad:
                audio_path = record_vad()
                if audio_path is None:
                    print("  nothing detected, try again.")
                    continue
                question = transcribe(audio_path)
            else:
                audio_path = record_fixed(record_seconds)
                question = transcribe(audio_path)

            if not question:
                print("  nothing heard, try again.")
                continue

            # -- Exit check ---------------------------------------------------
            if question.lower().strip().rstrip("?.!") in EXIT_PHRASES:
                print("\nGoodbye.")
                speak("Goodbye. Thank you for using Bharat Benefits.")
                break

            # -- RAG + LLM + TTS ----------------------------------------------
            context = await retrieve(question, moss_client)
            answer = generate_answer(question, context, conversation_history)

            conversation_history.append({"role": "user", "content": question})
            conversation_history.append({"role": "assistant", "content": answer})

            speak(answer)

        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except httpx.HTTPStatusError as e:
            print(f"\nAPI error {e.response.status_code}: {e.response.text[:200]}")
            print("Retrying next turn ...")
            time.sleep(1)
        except Exception as e:
            print(f"\nERROR: {e}")
            print("Retrying next turn ...")
            time.sleep(1)


# -- Entry --------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Bharat Benefits Voice Agent")
    parser.add_argument(
        "--seconds",
        type=int,
        default=5,
        help="Recording window in seconds for fixed mode (default: 5)",
    )
    parser.add_argument(
        "--vad",
        action="store_true",
        help="Use voice activity detection - stops recording when you pause",
    )
    parser.add_argument(
        "--text-mode",
        action="store_true",
        help="Type questions instead of speaking (for debugging)",
    )
    args = parser.parse_args()
    asyncio.run(
        live_loop(
            record_seconds=args.seconds,
            use_vad=args.vad,
            text_mode=args.text_mode,
        )
    )


if __name__ == "__main__":
    main()

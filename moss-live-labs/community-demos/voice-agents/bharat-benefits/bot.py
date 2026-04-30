"""
bot.py - Bharat Benefits Voice Agent
============================================
Continuous voice loop:

    mic -> Sarvam STT -> Moss RAG -> Sarvam LLM -> Sarvam TTS -> speaker
           (repeats until you say "exit" or press Ctrl+C)

Usage:
    python bot.py                 # default 5s recording per turn
    python bot.py --seconds 8     # longer recording window
    python bot.py --text-mode     # type instead of speak (debug)

Environment (.env):
    SARVAM_API_KEY     - Sarvam subscription key
    MOSS_PROJECT_ID    - InferEdge Moss project ID
    MOSS_PROJECT_KEY   - InferEdge Moss project key
    MOSS_INDEX_NAME    - default: bharat-benefits
    SARVAM_STT_MODEL   - default: saaras:v3
    SARVAM_CHAT_MODEL  - default: sarvam-105b
    SARVAM_TTS_MODEL   - default: bulbul:v3
    SARVAM_TTS_SPEAKER - default: priya

Install:
    pip install inferedge-moss httpx python-dotenv sounddevice soundfile numpy simpleaudio
"""

import argparse
import asyncio
import base64
import os
import re
import sys
import tempfile
import time
from pathlib import Path

import httpx
import sounddevice as sd
import soundfile as sf
import numpy as np
from dotenv import load_dotenv

# -- Config -------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=SCRIPT_DIR / ".env")

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
STT_MODEL      = os.getenv("SARVAM_STT_MODEL",   "saaras:v3")
CHAT_MODEL     = os.getenv("SARVAM_CHAT_MODEL",  "sarvam-105b")
TTS_MODEL      = os.getenv("SARVAM_TTS_MODEL",   "bulbul:v3")
TTS_SPEAKER    = os.getenv("SARVAM_TTS_SPEAKER", "priya")

MOSS_PROJECT_ID  = os.getenv("MOSS_PROJECT_ID", "")
MOSS_PROJECT_KEY = os.getenv("MOSS_PROJECT_KEY", "")
MOSS_INDEX_NAME  = os.getenv("MOSS_INDEX_NAME", "bharat-benefits")

SARVAM_BASE   = "https://api.sarvam.ai"
SAMPLE_RATE   = 16_000  # Hz - required by Sarvam STT
TOP_K         = 3
MAX_TTS_CHARS = 1500

EXIT_PHRASES = {"exit", "quit", "stop", "bye", "goodbye", "band karo", "band kar", "बंद करो"}

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
    return {"Authorization": f"Bearer {SARVAM_API_KEY}", "Content-Type": "application/json"}

def _check_env():
    missing = [v for v in ["SARVAM_API_KEY", "MOSS_PROJECT_ID", "MOSS_PROJECT_KEY"]
               if not os.getenv(v)]
    if missing:
        print(f"ERROR: missing environment variables: {', '.join(missing)}", file=sys.stderr)
        print("Set them in your .env file and try again.", file=sys.stderr)
        sys.exit(1)


# -- Step 1: Record from mic --------------------------------------------------

def record_audio(seconds: int = 5) -> Path:
    """Record from microphone. Returns path to a temp WAV file."""
    print(f"\nListening ({seconds}s) ...")
    try:
        audio = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE,
                       channels=1, dtype="int16")
        sd.wait()
    except Exception as e:
        print(f"ERROR: microphone unavailable: {e}", file=sys.stderr)
        sys.exit(1)

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    sf.write(tmp.name, audio, SAMPLE_RATE, subtype="PCM_16")
    tmp.close()
    return Path(tmp.name)


# -- Step 2: Speech to text (Sarvam STT) --------------------------------------

def transcribe(audio_path: Path) -> str:
    """Send audio to Sarvam STT. Returns transcript string."""
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


# -- Step 3: Moss RAG retrieval -----------------------------------------------

async def retrieve(question: str, moss_client) -> str:
    """Query Moss index for relevant context."""
    try:
        from inferedge_moss import QueryOptions
    except ImportError:
        print("ERROR: run: pip install inferedge-moss", file=sys.stderr)
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


# -- Step 4: Generate answer (Sarvam Chat) ------------------------------------

def generate_answer(question: str, context: str, history: list) -> str:
    """Generate a voice-friendly answer. Maintains conversation history."""
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
            "temperature": 0.2
        },
        timeout=60.0,
    )
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"].strip()
    answer = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    preview = answer[:120] + ("..." if len(answer) > 120 else "")
    print(f"   answer: {preview}")
    return answer


# -- Step 5: Text to speech (Sarvam TTS) --------------------------------------

def speak(answer: str) -> None:
    """Convert answer to speech and play it immediately."""
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

async def live_loop(record_seconds: int = 5, text_mode: bool = False):
    """Continuous voice-to-voice loop."""
    try:
        from inferedge_moss import MossClient
    except ImportError:
        print("ERROR: run: pip install inferedge-moss", file=sys.stderr)
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

    print("-" * 40)
    print("  Bharat Benefits - Voice Agent")
    print("  Say 'exit' or press Ctrl+C to stop.")
    print("-" * 40)

    while True:
        turn += 1
        print(f"\n[turn {turn}]")

        try:
            if text_mode:
                try:
                    question = input("  question: ").strip()
                except (KeyboardInterrupt, EOFError):
                    break
            else:
                audio_path = record_audio(record_seconds)
                question   = transcribe(audio_path)

            if not question:
                print("  nothing heard, try again.")
                continue

            if question.lower().strip().rstrip("?.!") in EXIT_PHRASES:
                print("\nGoodbye.")
                speak("Goodbye. Thank you for using Bharat Benefits.")
                break

            context = await retrieve(question, moss_client)
            answer  = generate_answer(question, context, conversation_history)

            conversation_history.append({"role": "user",      "content": question})
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
    parser.add_argument("--seconds",   type=int, default=5,
                        help="Recording duration per turn in seconds (default: 5)")
    parser.add_argument("--text-mode", action="store_true",
                        help="Type questions instead of speaking (for debugging)")
    args = parser.parse_args()
    asyncio.run(live_loop(record_seconds=args.seconds, text_mode=args.text_mode))


if __name__ == "__main__":
    main()
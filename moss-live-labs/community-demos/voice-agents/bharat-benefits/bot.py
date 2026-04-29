"""
bot.py – Bharat Benefits Voice Agent
=====================================
End-to-end voice RAG loop:

    voice/audio input
    -> Sarvam STT  (saaras:v3)
    -> Moss retrieval over scheme knowledge base
    -> Sarvam Chat Completion  (sarvam-m / sarvam-105b)
    -> Sarvam TTS  (bulbul:v1)
    -> audio response saved as response.wav (played if possible)

Usage:
    python bot.py --text   "I am a small farmer. Which scheme can help me?"
    python bot.py --audio  path/to/question.wav
    python bot.py --record-seconds 5          # record from microphone

Environment variables (via .env):
    SARVAM_API_KEY    – Sarvam subscription key
    SARVAM_STT_MODEL  – default: saaras:v3
    SARVAM_CHAT_MODEL – default: sarvam-105b
    SARVAM_TTS_MODEL  – default: bulbul:v3
    SARVAM_TTS_SPEAKER– default: priya
    MOSS_PROJECT_ID
    MOSS_PROJECT_KEY
    MOSS_INDEX_NAME   – default: bharat-benefits
"""

import argparse
import re
import asyncio
import base64
import os
import sys
import tempfile
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Load environment
SCRIPT_DIR = Path(__file__).resolve().parent

# Load .env from the same folder as this script — works whether you
# cd into the folder or call it as:  python path/to/bot.py
load_dotenv(dotenv_path=SCRIPT_DIR / ".env")

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
STT_MODEL = os.getenv("SARVAM_STT_MODEL", "saaras:v3")
CHAT_MODEL = os.getenv("SARVAM_CHAT_MODEL", "sarvam-m")
TTS_MODEL = os.getenv("SARVAM_TTS_MODEL", "bulbul:v1")
TTS_SPEAKER = os.getenv("SARVAM_TTS_SPEAKER", "anushka")

MOSS_PROJECT_ID = os.getenv("MOSS_PROJECT_ID", "")
MOSS_PROJECT_KEY = os.getenv("MOSS_PROJECT_KEY", "")
MOSS_INDEX_NAME = os.getenv("MOSS_INDEX_NAME", "bharat-benefits")

SARVAM_BASE = "https://api.sarvam.ai"
TOP_K = 3  # number of Moss results to retrieve

# Save TTS audio next to the script, not in the caller's working directory
OUTPUT_AUDIO = SCRIPT_DIR / "response.wav"

SYSTEM_PROMPT = """You are Bharat Benefits Voice Agent, a voice assistant that answers questions \
about Indian public-benefit schemes using only the retrieved context provided below.

Rules:
- Answer ONLY from the retrieved context. Do not invent eligibility rules, amounts, or deadlines.
- If the context is insufficient, say: "The demo knowledge base does not have enough information \
about this. Please check the official government portal for accurate details."
- Keep answers concise, practical, and easy to understand — suitable for listening, not reading.
- Use short paragraphs, no tables, no bullet markdown formatting in your spoken answer.
- Always suggest the user verify final details on the official government portal.
- Mention the relevant helpline number if available in the context."""


# Environment checks


def _check_env() -> None:
    missing = []
    if not SARVAM_API_KEY:
        missing.append("SARVAM_API_KEY")
    if not MOSS_PROJECT_ID:
        missing.append("MOSS_PROJECT_ID")
    if not MOSS_PROJECT_KEY:
        missing.append("MOSS_PROJECT_KEY")
    if missing:
        print(
            "\n[ERROR] Missing environment variables:\n"
            + "\n".join(f"  {v}" for v in missing)
            + "\n\nCopy .env.example -> .env and fill in your credentials.\n",
            file=sys.stderr,
        )
        sys.exit(1)


# Sarvam helpers


def _sarvam_headers_key() -> dict:
    """Headers for endpoints that use api-subscription-key."""
    return {"api-subscription-key": SARVAM_API_KEY}


def _sarvam_headers_bearer() -> dict:
    """Headers for Chat Completion which uses Bearer auth."""
    return {
        "Authorization": f"Bearer {SARVAM_API_KEY}",
        "Content-Type": "application/json",
    }


def transcribe_audio(audio_path: str | Path) -> str:
    """
    Send an audio file to Sarvam STT (saaras:v3).
    Returns the transcribed text string.
    """
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    print(f"\nTranscribing audio: {audio_path.name}")

    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    # Detect a rough MIME type from extension
    ext = audio_path.suffix.lower()
    mime_map = {
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
        ".m4a": "audio/mp4",
    }
    mime = mime_map.get(ext, "audio/wav")

    try:
        response = httpx.post(
            f"{SARVAM_BASE}/speech-to-text",
            headers=_sarvam_headers_key(),
            files={"file": (audio_path.name, audio_bytes, mime)},
            data={
                "model": STT_MODEL,
                "language_code": "unknown",  # auto-detect language
            },
            timeout=60.0,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        print(
            f"\n[ERROR] Sarvam STT API returned {exc.response.status_code}: "
            f"{exc.response.text}\n",
            file=sys.stderr,
        )
        raise

    data = response.json()
    transcript = data.get("transcript", "").strip()
    lang = data.get("language_code", "unknown")
    print(f"   Detected language : {lang}")
    print(f"   Transcript        : {transcript!r}")
    return transcript


def generate_answer(question: str, retrieved_context: str) -> str:
    """
    Send question + retrieved context to Sarvam Chat Completion.
    Returns the generated answer string.
    """
    print(f"\nGenerating answer with {CHAT_MODEL}")

    user_message = (
        f"User question:\n{question}\n\n"
        f"Retrieved context:\n{retrieved_context}\n\n"
        "Answer requirements:\n"
        "- Use only the retrieved context above.\n"
        "- Be concise and voice-friendly (no markdown tables or long bullet lists).\n"
        "- Mention relevant documents or next steps when available.\n"
        "- End with a verification caveat: tell the user to check the official portal.\n"
    )

    payload = {
        "model": CHAT_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": 512,
        "temperature": 0.2,
    }

    try:
        response = httpx.post(
            f"{SARVAM_BASE}/v1/chat/completions",
            headers=_sarvam_headers_bearer(),
            json=payload,
            timeout=60.0,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        print(
            f"\n[ERROR] Sarvam Chat API returned {exc.response.status_code}: "
            f"{exc.response.text}\n",
            file=sys.stderr,
        )
        raise

    data = response.json()
    raw = data["choices"][0]["message"]["content"].strip()
    answer = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    return answer


def text_to_speech(answer: str, output_path: str | Path = OUTPUT_AUDIO) -> Path:
    """
    Convert the answer text to audio using Sarvam TTS (bulbul:v1).
    Saves the WAV file to output_path and returns the path.
    """
    output_path = Path(output_path)
    print(f"\nConverting answer to speech (speaker: {TTS_SPEAKER}) ...")

    # Sarvam TTS accepts up to 1500 chars for bulbul:v1; truncate gracefully
    max_chars = 1500
    text_for_tts = answer[:max_chars]
    if len(answer) > max_chars:
        print(f"   Warning: Answer truncated to {max_chars} chars for TTS.")

    payload = {
        "text": text_for_tts,
        "target_language_code": "en-IN",  # answer is always in English for now
        "speaker": TTS_SPEAKER,
        "model": TTS_MODEL,
        "enable_preprocessing": True,
    }

    try:
        response = httpx.post(
            f"{SARVAM_BASE}/text-to-speech",
            headers={**_sarvam_headers_key(), "Content-Type": "application/json"},
            json=payload,
            timeout=60.0,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        print(
            f"\n[ERROR] Sarvam TTS API returned {exc.response.status_code}: "
            f"{exc.response.text}\n",
            file=sys.stderr,
        )
        raise

    data = response.json()
    audios = data.get("audios", [])
    if not audios:
        raise ValueError("Sarvam TTS returned no audio data.")

    # Decode the first base64-encoded audio chunk
    wav_bytes = base64.b64decode(audios[0])
    output_path.write_bytes(wav_bytes)
    print(f"   Saved TTS audio -> {output_path}")
    return output_path


# Moss retrieval


async def retrieve_context(question: str) -> str:
    """
    Load the Moss index and query it with the user's question.
    Returns a formatted context string for the LLM prompt.
    """
    try:
        from inferedge_moss import MossClient, QueryOptions
    except ImportError:
        print(
            "\n[ERROR] inferedge-moss is not installed.\n"
            "Run:  pip install -r requirements.txt\n",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"\nQuerying Moss index '{MOSS_INDEX_NAME}' (top_k={TOP_K}) ...")

    client = MossClient(MOSS_PROJECT_ID, MOSS_PROJECT_KEY)

    try:
        await client.load_index(MOSS_INDEX_NAME)
    except Exception as exc:
        print(
            f"\n[ERROR] Could not load Moss index '{MOSS_INDEX_NAME}': {exc}\n"
            "Have you run  python create_index.py  yet?\n",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        results = await client.query(
            MOSS_INDEX_NAME,
            question,
            QueryOptions(top_k=TOP_K, alpha=0.75),  # hybrid: semantic-heavy
        )
    except Exception as exc:
        print(f"\n[ERROR] Moss query failed: {exc}\n", file=sys.stderr)
        raise

    if not results.docs:
        print("   Warning: No relevant documents found in the knowledge base.")
        return "No relevant information was found in the knowledge base."

    print(f"   Retrieved {len(results.docs)} snippet(s):")
    context_parts = []
    for i, doc in enumerate(results.docs, 1):
        source = (doc.metadata or {}).get("source", doc.id)
        score = getattr(doc, "score", 0.0)
        snippet = doc.text[:300].replace("\n", " ")  # brief preview in logs
        print(f'   [{i}] {source}  (score={score:.3f})  "{snippet}..."')
        context_parts.append(f"[Source: {source}]\n{doc.text}")

    return "\n\n---\n\n".join(context_parts)


# Microphone recording


def record_from_microphone(seconds: int) -> Path:
    """
    Record `seconds` of audio from the default microphone.
    Saves to a temp WAV file and returns its path.
    Falls back gracefully if sounddevice / soundfile are unavailable.
    """
    try:
        import numpy as np
        import sounddevice as sd
        import soundfile as sf
    except ImportError as exc:
        print(
            f"\n[ERROR] Microphone recording requires sounddevice, soundfile, and numpy.\n"
            f"Missing: {exc}\n"
            "Install with:  pip install sounddevice soundfile numpy\n"
            "Or use --text or --audio instead.\n",
            file=sys.stderr,
        )
        sys.exit(1)

    sample_rate = 16_000
    print(f"\nRecording {seconds}s from microphone ... (speak now)")
    try:
        audio = sd.rec(
            int(seconds * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
        )
        sd.wait()
    except Exception as exc:
        print(
            f"\n[ERROR] Microphone unavailable: {exc}\n"
            "Use --text or --audio to bypass microphone input.\n",
            file=sys.stderr,
        )
        sys.exit(1)

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    sf.write(tmp.name, audio, sample_rate, subtype="PCM_16")
    print(f"   Saved recording -> {tmp.name}")
    return Path(tmp.name)


# Playback (best-effort)


def _try_play(wav_path: Path) -> None:
    """
    Play a WAV file. Press Ctrl+C at any time to stop playback immediately.
    Silently skips if simpleaudio is unavailable.
    """
    try:
        import simpleaudio as sa
    except ImportError:
        return  # playback is optional

    try:
        wave_obj = sa.WaveObject.from_wave_file(str(wav_path))
        play_obj = wave_obj.play()
        print("   Playing audio ... (press Ctrl+C to stop)")
        try:
            while play_obj.is_playing():
                play_obj.wait_done.__func__  # keep reference alive
                import time

                time.sleep(0.05)  # poll every 50 ms so Ctrl+C is responsive
        except KeyboardInterrupt:
            play_obj.stop()
            print("   Playback stopped by user.")
            return
        print("   Playback finished.")
    except Exception:
        pass  # Playback is optional; audio is always saved to disk


# Main pipeline


async def run_pipeline(question: str) -> None:
    """Run the full STT->Moss->LLM->TTS pipeline for a given text question."""

    print("\n" + "=" * 60)
    print("  Bharat Benefits Voice Agent")
    print("=" * 60)
    print(f"\nQuestion: {question}")

    # 1. Moss retrieval
    context = await retrieve_context(question)

    # 2. Chat completion
    answer = generate_answer(question, context)
    print(f"\nAnswer:\n{answer}")

    # 3. TTS
    try:
        wav_path = text_to_speech(answer)
        _try_play(wav_path)
    except KeyboardInterrupt:
        # Ctrl+C during playback is already handled inside _try_play;
        # catching here ensures the pipeline exits cleanly without a traceback.
        print("\nStopped. Audio saved to:", OUTPUT_AUDIO)
    except Exception as exc:
        print(f"\nTTS failed ({exc}). Printed answer above is still valid.")

    print("\nDone.\n")


async def main_async(args: argparse.Namespace) -> None:
    _check_env()

    # Determine input mode
    if args.text:
        question = args.text

    elif args.audio:
        question = transcribe_audio(args.audio)
        if not question:
            print("[ERROR] STT returned an empty transcript.", file=sys.stderr)
            sys.exit(1)

    elif args.record_seconds:
        tmp_audio = record_from_microphone(args.record_seconds)
        question = transcribe_audio(tmp_audio)
        if not question:
            print("[ERROR] STT returned an empty transcript.", file=sys.stderr)
            sys.exit(1)

    else:
        # Interactive: ask user to type
        try:
            question = input(
                "\nType your question (or press Ctrl+C to exit):\n> "
            ).strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            sys.exit(0)
        if not question:
            print("[ERROR] Empty question.", file=sys.stderr)
            sys.exit(1)

    await run_pipeline(question)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bharat Benefits Voice Agent – voice RAG for Indian public-benefit schemes"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--text",
        metavar="QUESTION",
        help='Ask a question as plain text, e.g.: --text "Which scheme helps small farmers?"',
    )
    group.add_argument(
        "--audio",
        metavar="FILE",
        help="Path to an audio file (WAV/MP3/etc.) containing a spoken question.",
    )
    group.add_argument(
        "--record-seconds",
        type=int,
        metavar="N",
        help="Record N seconds from the microphone and transcribe.",
    )
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()

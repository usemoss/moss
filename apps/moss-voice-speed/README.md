# Moss voice-agent speed showcase

A real, local, **runnable** voice agent (Pipecat) that grounds every reply in a Moss
index — and shows how Moss's sub‑10ms in‑process retrieval keeps the agent snappy.

- Talk to it in your browser (Pipecat's WebRTC runner). **No Docker, no Agora.**
- Every turn prints the retrieval latency, e.g. `⚡ retrieval [Moss (in-process)] · Moss lookup 2 ms · added to this turn ≈ 2 ms`.
- Flip one env var to simulate a **remote vector‑DB** round trip and *hear* the same agent lag.

Pipeline: **Deepgram** (STT) → **Moss** (retrieval) → **OpenAI** (LLM) → **ElevenLabs** (TTS).

## Prerequisites

- Python 3.10–3.12 (managed automatically by `uv`).
- Keys: Moss (`project_id`/`project_key`), Deepgram, OpenAI, ElevenLabs.
- [`uv`](https://docs.astral.sh/uv/).

## Run it

```bash
cd apps/moss-voice-speed
uv sync                       # creates the venv, installs Pipecat + Moss
cp .env.example .env          # paste your keys

# ten-moss isn't needed here; this agent uses the `moss` SDK directly.
python create_index.py        # build the demo index once (MOSS_INDEX_NAME)

python bot.py                 # prints a localhost URL — open it, click Connect, talk
```

Ask it: *“How long do refunds take?”*, *“Which payment methods can I use?”*, *“How fast is express shipping?”* — it answers from the knowledge base, and each turn logs the retrieval time.

## The showcase: Moss vs a remote vector DB

Same agent, same questions — the only change is where retrieval happens. Run each and
listen to how quickly it starts replying:

```bash
# Fast path — Moss retrieves in-process (~2 ms per turn)
SIMULATE_REMOTE_MS=0 python bot.py

# What a remote vector DB costs you — ~400 ms added to every turn
SIMULATE_REMOTE_MS=400 python bot.py
```

In remote‑sim mode the reply is the same (it's still grounded), but the agent visibly
pauses before each answer — the round‑trip latency you avoid by keeping retrieval in
process with Moss. For a live A/B in front of leadership, run two terminals side by side
(`SIMULATE_REMOTE_MS=0` and `=400`) and ask both the same question.

> `SIMULATE_REMOTE_MS=400` is a stand‑in for a typical cloud vector‑DB round trip
> (200–500 ms; see the repo's `benchmarks/`). To make the "before" a *real* remote store
> instead of a simulated delay, point `_ground()` in `moss_speed_retrieval.py` at that
> store — the rest of the agent is unchanged.

## What to look for

- **Retrieval line per turn** in the terminal — the headline number.
- **Time‑to‑first‑word**: in Moss mode the agent answers almost immediately after you stop
  speaking; in remote‑sim mode there's an audible gap before every reply.
- The index loads once at startup (a one‑time cost); every turn after that is the fast path.

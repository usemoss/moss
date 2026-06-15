# Moss + Google ADK Cookbook

Use [Moss](https://moss.dev) sub-10 ms semantic search as a retrieval tool for [Google's Agent Development Kit (ADK)](https://github.com/google/adk-python) - including inside the **Gemini Live API** for real-time voice agents.

## Why

In a voice agent, every tool call delays the assistant's spoken reply by however long the tool takes. Most vector databases add 200-500 ms per call, which a user hears as a noticeable "...uhh..." pause. Moss adds under 10 ms, so retrieval disappears from the latency budget and the conversation stays fluid.

That's the whole reason this cookbook exists.

## Install

```bash
pip install moss google-adk python-dotenv
```

## Setup

Copy `.env.example` to `.env` and fill in:

```env
MOSS_PROJECT_ID=...
MOSS_PROJECT_KEY=...
MOSS_INDEX_NAME=moss-adk-demo-index
GOOGLE_API_KEY=...
ADK_MODEL=gemini-3.1-flash-live-preview
```

Google AI Studio key: <https://aistudio.google.com/app/apikey>. Moss credentials from [moss.dev](https://moss.dev) (free tier).

`ADK_MODEL` must be a Gemini Live model. This cookbook is voice-only. We default to the half-cascade preview (`gemini-3.1-flash-live-preview`) because its function-calling path is stable; native-audio preview models can stall in extended thinking when tools are involved.

## Quickstart: voice agent

Two paths. **Path A is the recommended one** because the browser handles acoustic echo cancellation for free; the CLI demo will echo on speakers (see [Audio limitations](#audio-limitations)).

### Path A: browser via `adk web` (recommended)

From the cookbook directory:

```bash
# macOS: needed for the Live API WebSocket to validate certs
export SSL_CERT_FILE=$(python3 -m certifi)

adk web
```

Open the URL it prints (usually <http://localhost:8000>), pick `moss_agent`, click the microphone. Speak: *"How long do refunds take?"* or *"What's your return policy?"*

The first call seeds a tiny demo index in your Moss project; subsequent calls reuse it.

### Path B: CLI

```bash
pip install sounddevice         # plus `brew install portaudio` on macOS
python voice_demo.py
```

Mic-in / speaker-out, all wired up in one Python file. **Use headphones** - the CLI does no echo cancellation (see below).

### What you should notice

In both paths, watch the tool-call log:

```text
[tool] moss_search({'query': 'How long do refunds take?'})
```

The audio reply starts essentially immediately after that line prints. With a remote vector DB you'd hear a clear pause between question and answer; with Moss you don't.

## Audio limitations

**The Gemini Live API does no server-side acoustic echo cancellation (AEC).** If the model's audio output reaches the microphone, the API's VAD will transcribe it as new user speech and the model will respond to itself, looping. This is a known limitation acknowledged by Google in their [official Python CLI example README](https://github.com/google-gemini/gemini-live-api-examples/blob/main/command-line/python/README.md) ("use headphones") and tracked in [cookbook issue #1197](https://github.com/google-gemini/cookbook/issues/1197) against `gemini-3.1-flash-live-preview` specifically.

| Path | AEC story |
| ---- | --------- |
| `adk web` (Path A) | Browser applies WebRTC AEC automatically. No echo. |
| `voice_demo.py` (Path B) on **headphones** | Speaker-to-mic feedback path is cut. No echo. |
| `voice_demo.py` (Path B) on **speakers** | Will echo-loop. Either use headphones, mute mic while the model speaks, or run through a stack that does AEC (LiveKit, SIP gateway, browser). |

For production voice deployments the canonical answer is to put a platform with AEC in front of the Live API - browser via WebRTC, [LiveKit](https://docs.livekit.io/agents/models/realtime/plugins/gemini/), or a SIP/telephony gateway.

## Files

| File | Purpose |
| ---- | ------- |
| `moss_agent/__init__.py` | Marks the package so `adk web` discovers it. |
| `moss_agent/agent.py` | Defines `root_agent` for `adk web`. |
| `moss_agent/moss_search.py` | `make_moss_search(...)` factory: returns `(load_index, moss_search)`. |
| `voice_demo.py` | Runnable CLI voice demo (mic in / speaker out, Gemini Live BIDI). |
| `.env.example` | Required environment variables. |

## Using the tool in your own agent

```python
from google.adk.agents import Agent
from moss_agent.moss_search import make_moss_search

load_index, moss_search = make_moss_search(
    index_name="support-docs", top_k=5, alpha=0.8
)
await load_index()  # warm the index before serving any traffic

agent = Agent(
    name="support",
    model="gemini-3.1-flash-live-preview",
    instruction="Answer using the `moss_search` tool.",
    tools=[moss_search],
)
```

`moss_search` is a plain async function. ADK auto-wraps it in `FunctionTool`; the docstring becomes the tool description shown to the model and `query: str` becomes its single argument.

## Embedding in a custom WebSocket app

For production voice deployments (e.g. mobile clients, telephony bridges), fork the [ADK bidi-demo](https://github.com/google/adk-samples/tree/main/python/agents/bidi-demo) and replace its `google_search_agent` with `moss_agent` here. The bidi-demo is the canonical FastAPI + WebSocket scaffold; the Moss tool drops in with no changes.

## Tuning

- `top_k` (default `5`): how many docs to return per call. Smaller is faster and cheaper in tokens.
- `alpha` (default `0.8`): hybrid search blend. `1.0` is pure semantic, `0.0` is pure keyword (BM25). `0.8` works well for natural-language voice questions.

## Next steps

- Swap `SEED_DOCS` in `voice_demo.py` for your own data, or point `MOSS_INDEX_NAME` at an existing Moss index.
- For per-session indexes (e.g. per-caller knowledge base, swap mid-call), call `make_moss_search(...)` per session instead of at module scope; see the [airline-pnr voice agent](../../voice-agents/airline-pnr/) for the pattern.

See the [Moss docs](https://docs.moss.dev) for hybrid search, metadata filters, and the full SDK reference.

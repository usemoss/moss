# Moss + Google ADK Cookbook

Use [Moss](https://moss.dev) sub-10 ms semantic search as a retrieval tool for [Google's Agent Development Kit (ADK)](https://github.com/google/adk-python).

## Why

Tool calls block the assistant's turn. Most vector databases add 200-500 ms per call, which is visible to a user in any real-time conversation. Moss adds under 10 ms, so retrieval drops out of the latency budget. That matters most in ADK's **Live (BIDI)** mode, where the agent talks to the user over the Gemini Live API in real time.

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
```

Get a Google AI Studio key at <https://aistudio.google.com/app/apikey>. Moss credentials come from [moss.dev](https://moss.dev) (free tier available).

## Quickstart

```bash
python demo.py
```

The script:

1. Seeds a tiny support-docs index in your Moss project (idempotent).
2. Builds an ADK `Agent` with `moss_search` as its only tool.
3. Runs one question through `InMemoryRunner` and prints the response and tool calls.

## Files

| File | Purpose |
| ---- | ------- |
| `moss_adk.py` | `MossSearchTool` wrapper; exposes an async tool function for ADK. |
| `agent.py` | Defines `root_agent` for `adk run .` and `adk web`. |
| `demo.py` | Runnable **text** demo with seed data. |
| `voice_demo.py` | Runnable **voice** demo (CLI, mic in / speaker out, Gemini Live). |
| `.env.example` | Required environment variables. |

## Using the tool in your own agent

```python
from google.adk.agents import Agent
from moss_adk import MossSearchTool

moss = MossSearchTool(index_name="support-docs", top_k=5, alpha=0.8)

agent = Agent(
    name="support",
    model="gemini-2.5-flash",
    instruction="Answer using the `moss_search` tool.",
    tools=[moss.search_tool],
)
```

`MossSearchTool.search_tool` is an async function ADK introspects for its schema. The docstring becomes the tool description shown to the model; the `query: str` parameter becomes its single argument.

## Live (BIDI) voice mode

The same Moss tool works inside ADK's bidirectional voice streaming. Three ways to try it:

**1. CLI voice demo (`voice_demo.py`)** — single Python file, mic in / speaker out:

```bash
pip install sounddevice         # plus `brew install portaudio` on macOS
python voice_demo.py
```

Speak a question like "How long do refunds take?" and the agent replies with audio. The `moss_search` tool runs inside the audio loop with no perceptible pause thanks to Moss's sub-10 ms retrieval.

**2. ADK dev UI** (browser, zero code):

```bash
adk web
```

Open the URL it prints, pick `moss_support_agent`, click the microphone. Set `ADK_MODEL=gemini-2.5-flash-native-audio-preview-12-2025` in `.env` first so the agent boots in audio mode.

**3. Custom FastAPI + WebSocket** (for embedding in your own app): fork the [ADK bidi-demo](https://github.com/google/adk-samples/tree/main/python/agents/bidi-demo) and replace its `google_search_agent` with the agent in `agent.py`.

## Tuning

- `top_k` (default `5`): how many docs to return per call. Smaller is faster and cheaper in tokens.
- `alpha` (default `0.8`): hybrid search blend. `1.0` is pure semantic, `0.0` is pure keyword (BM25). `0.8` works well for natural-language questions.

## Next steps

- Swap `SEED_DOCS` in `demo.py` for your own data, or point `MOSS_INDEX_NAME` at an existing Moss index.
- For per-session indexes (e.g. per-user, per-call), construct a fresh `MossSearchTool` on session start instead of as a module global; see the [airline-pnr voice agent](../../voice-agents/airline-pnr/) for the pattern.

See the [Moss docs](https://docs.moss.dev) for hybrid search, metadata filters, and the full SDK reference.

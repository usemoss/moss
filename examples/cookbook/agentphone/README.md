# Moss AgentPhone Cookbook

A single-file webhook server that backs an [AgentPhone](https://agentphone.ai)
phone number with [Moss](https://moss.dev) semantic search. The model
runs in a Claude tool-call loop with `moss_search` as the only tool.
Voice only.

Mirrors the structure of AgentPhone's reference example:
[Calls guide - "Example: tool-calling handler"](https://docs.agentphone.ai/documentation/guides/calls).

## Call flow

```
   caller
     |
     | speaks
     v
  AgentPhone   --(signed webhook)-->   server.py
   ^                                       |
   |                                       | run_tool_call(transcript, history)
   |                                       |    Claude --(tool_use)--> moss_search --> Moss
   |                                       |    Claude <-(tool_result)
   |                                       v
   |                                  NDJSON streamed back
   |
   speaks reply
```

## Why this shape

Realtime voice models often emit an ungrounded reply before a tool
returns. AgentPhone's webhook-voice mode inverts that: AgentPhone has
nothing to speak until your handler returns text, so the spoken answer
is always built from whatever `moss_search` produced. Tool calling lets
the model rewrite the user's question into a focused search query and
skip retrieval entirely on small talk.

## Files

| File | Description |
|------|-------------|
| `server.py` | Module-level `TOOLS` / `TOOL_HANDLERS` / `run_tool_call` + the FastAPI webhook |
| `create_index.py` | One-time script to seed the Moss demo index |
| `test_integration.py` | Mocked unit tests |
| `pyproject.toml` | Package metadata |
| `.env.example` | Template for required environment variables |

## Installation

```bash
cd examples/cookbook/agentphone
uv sync
```

## Setup

Copy `.env.example` to `.env` and fill in:

```env
MOSS_PROJECT_ID=...
MOSS_PROJECT_KEY=...
MOSS_INDEX_NAME=agentphone-demo-index
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-haiku-4-5-20251001
AGENTPHONE_WEBHOOK_SECRET=whsec_...
PORT=8000
```

`AGENTPHONE_WEBHOOK_SECRET` is returned when you register the webhook
(step 2 of "Wire it up" below).

## Create the demo index (one time)

```bash
uv run python create_index.py
```

Seeds a small index (refunds, returns, shipping, support hours, password
reset). Skips if the index already exists.

## Run the server

```bash
uv run python server.py
```

Listens on `http://localhost:8000/webhook` and `/healthz`.

## Wire it up to AgentPhone

1. Expose the local server publicly:
   ```bash
   ngrok http 8000
   ```
2. Register the public URL with AgentPhone:
   ```bash
   curl -X POST https://api.agentphone.ai/v1/webhooks \
     -H "Authorization: Bearer $AGENTPHONE_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://<your-ngrok-host>/webhook"}'
   ```
   Copy the returned `secret` into `AGENTPHONE_WEBHOOK_SECRET` and
   restart the server.
3. Create an agent with `voiceMode: "webhook"` and attach a voice-capable
   number to it.
4. Call the number, or place a browser test call via
   `POST /v1/calls/web`.

## What success looks like

A caller speaking once produces these log lines (`channel=voice`, two
Anthropic calls = one tool round-trip with Moss):

```
delivery=voice_... event=agent.message channel=voice
POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
"POST /webhook HTTP/1.1" 200 OK
```

Small talk that doesn't trigger retrieval shows only one Anthropic call.

## Run the tests

```bash
uv run python test_integration.py
```

Tests cover signature verification, the tool-call loop with and without
a tool, and `recentHistory` -> Anthropic-message mapping.

## How it reads

The whole integration is in `server.py` and reads top-to-bottom:

1. env + clients
2. system prompt
3. `TOOLS` schema
4. `_moss_search` handler + `TOOL_HANDLERS` dict
5. `run_tool_call` loop (bounded at 5 iterations, exits on
   `stop_reason != "tool_use"`)
6. `verify_webhook_signature` (HMAC-SHA256)
7. FastAPI `/webhook` route: verify, route, stream NDJSON

## Notes

- SMS / iMessage are out of scope for this cookbook. AgentPhone replies
  to text channels through `POST /v1/messages`, not the webhook response
  body, and US SMS additionally needs 10DLC registration. Voice is the
  path the AgentPhone reference example shows, and it works without any
  per-account compliance steps.
- `recentHistory` from the webhook payload is threaded into Claude's
  `messages` so the model has prior turns of context. Without this the
  agent loses memory between turns of the same call.
- Any chat client that exposes a tools-aware `messages.create`-shaped
  API works; the cookbook uses `anthropic.AsyncAnthropic` to match
  AgentPhone's reference example.

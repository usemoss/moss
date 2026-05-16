# Moss AgentPhone Cookbook

A small webhook-server cookbook that backs an
[AgentPhone](https://agentphone.ai) phone number with
[Moss](https://moss.dev) semantic search. The FastAPI entrypoint is in
`server.py`, reusable logic (tool schema, tool-call loop, signature
verification) is in `moss_agentphone.py`, and one-time index setup is
in `create_index.py`. The model runs in a Claude tool-call loop with
`moss_search` as the only tool. Voice only.

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
| `moss_agentphone.py` | Reusable cookbook content: `TOOLS`, `run_tool_call`, `verify_webhook_signature`, history mapping, NDJSON + Moss-log helpers |
| `server.py` | FastAPI shell: env, clients, `_moss_search` handler, `/webhook` route |
| `create_index.py` | One-time script to seed the Moss demo index |
| `test_integration.py` | Mocked unit tests |
| `pyproject.toml` | Package metadata |
| `railway.json` | Railway deploy config (start command + healthcheck) |
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
(step 1 of "Wire it up" below).

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

## Expose the local server (ngrok)

AgentPhone needs to POST webhooks to a public HTTPS URL. Your laptop's
`localhost:8000` is not reachable from the internet, so you need a
tunnel. ngrok is the quickest option; cloudflared or any other tunnel
works equivalently.

One-time setup:

```bash
brew install ngrok
# sign up free at https://ngrok.com to get an auth token, then:
ngrok config add-authtoken <YOUR_TOKEN>
```

In a separate terminal (keep it open the whole time you are testing):

```bash
ngrok http 8000
```

ngrok prints something like:

```
Forwarding   https://abc123.ngrok-free.dev -> http://localhost:8000
```

Copy that `https://abc123.ngrok-free.dev` URL. That is the public address
AgentPhone will POST to; ngrok forwards every request to your local
server. The URL changes each time you restart ngrok on the free tier,
so you will need to re-register the webhook if you stop the tunnel.

Alternative: `cloudflared tunnel --url http://localhost:8000` (no signup
required) prints a `https://<random>.trycloudflare.com` URL you can use
the same way. Or deploy to Railway (see below) for a stable URL and
skip the tunnel entirely.

## Deploy to Railway

ngrok is good for local iteration; for anything you want to revisit
tomorrow, deploy the server somewhere with a persistent HTTPS URL.
This cookbook ships with a `railway.json` so the deploy is one click.

Before deploying, run `uv run python create_index.py` once locally with
the Moss credentials you plan to use on Railway. The index lives in
your Moss project, not on the server, so seeding it locally is enough
for Railway to query it.

1. Push the repo (including this cookbook) to GitHub if it isn't there
   already.
2. Go to https://railway.app -> "New Project" -> "Deploy from GitHub
   repo" -> pick your fork of the Moss repo.
3. In the Railway service's **Settings** tab:
   - **Root Directory**: `examples/cookbook/agentphone`
   - Railway will pick up `railway.json` from that directory and use
     the start command, healthcheck path, and Nixpacks builder
     configured there.
4. In the **Variables** tab, set everything from your `.env`:
   - `MOSS_PROJECT_ID`
   - `MOSS_PROJECT_KEY`
   - `MOSS_INDEX_NAME`
   - `ANTHROPIC_API_KEY`
   - `ANTHROPIC_MODEL`
   - `AGENTPHONE_WEBHOOK_SECRET` (use a placeholder for now; you will
     replace it after step 6)

   Do **not** set `PORT`; Railway injects it.
5. Click **Deploy**. Once the build is green, open the service and
   click **Settings -> Networking -> Generate Domain**. You will get a
   URL like `https://moss-agentphone-production.up.railway.app`.
6. Register the webhook against that URL with the AgentPhone API:
   ```bash
   curl -X POST https://api.agentphone.ai/v1/webhooks \
     -H "Authorization: Bearer $AGENTPHONE_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://<your-railway-domain>/webhook"}'
   ```
   Copy the `secret` from the response, paste it into the
   `AGENTPHONE_WEBHOOK_SECRET` variable in Railway, and let it
   redeploy.
7. Call your AgentPhone number. Railway's deployment logs show the
   same colored Moss block you saw locally.

If you had already registered the webhook against an ngrok URL, you
can swap it without losing the existing webhook id:

```bash
curl -X POST https://api.agentphone.ai/v1/webhooks \
  -H "Authorization: Bearer $AGENTPHONE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://<your-railway-domain>/webhook"}'
```

This rotates the secret. Update `AGENTPHONE_WEBHOOK_SECRET` in Railway
with the new value.

## Wire it up to AgentPhone

With the public URL in hand:

1. Register the webhook (use your AgentPhone API key, `sk_live_...`):
   ```bash
   curl -X POST https://api.agentphone.ai/v1/webhooks \
     -H "Authorization: Bearer $AGENTPHONE_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://<your-ngrok-host>/webhook"}'
   ```
   The response includes a `secret` (starts with `whsec_`). Paste it
   into `AGENTPHONE_WEBHOOK_SECRET` in `.env`, then restart the server.
2. Create an agent with `voiceMode: "webhook"` and attach a voice-capable
   phone number:
   ```bash
   curl -X POST https://api.agentphone.ai/v1/agents \
     -H "Authorization: Bearer $AGENTPHONE_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"name": "Moss Support Bot", "voiceMode": "webhook",
          "beginMessage": "Hi, thanks for calling. How can I help?"}'
   # then attach a number:
   curl -X POST https://api.agentphone.ai/v1/agents/<AGENT_ID>/numbers \
     -H "Authorization: Bearer $AGENTPHONE_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"numberId": "<NUMBER_ID>"}'
   ```
3. Call the number, or place a browser test call via
   `POST /v1/calls/web`.

## Troubleshooting

- **`401 invalid webhook signature`**: `AGENTPHONE_WEBHOOK_SECRET` in
  `.env` does not match what AgentPhone signed with. Re-check that you
  pasted the `whsec_...` from the `POST /v1/webhooks` response (not
  your `sk_live_...` API key).
- **ngrok URL keeps changing**: free tier gives a new URL each session.
  Either re-register the webhook each time, or deploy `server.py`
  somewhere with a stable URL.
- **Agent says "What are you building?"**: the AgentPhone agent's
  `beginMessage` is set to its starter value. `PATCH
  /v1/agents/{id}` with a new `beginMessage` to change it.

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

`moss_agentphone.py` (reusable, no env side effects):

1. `TOOLS` schema
2. `verify_webhook_signature` (HMAC-SHA256, with replay window)
3. `to_anthropic_history` (map AgentPhone `recentHistory` -> Claude messages)
4. `run_tool_call` loop (bounded at 5 iterations, exits on
   `stop_reason != "tool_use"`)
5. NDJSON + Moss-log helpers

`server.py` (FastAPI deployment shell):

1. env + clients (`MossClient`, `AsyncAnthropic`)
2. `SYSTEM_PROMPT`
3. `_moss_search` tool handler + `TOOL_HANDLERS` dict
4. `lifespan` hook (pre-load the Moss index)
5. `/webhook` route: verify signature, route by channel, stream NDJSON

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

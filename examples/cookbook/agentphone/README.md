# Moss AgentPhone Cookbook

This cookbook backs an [AgentPhone](https://agentphone.ai) phone number with
[Moss](https://moss.dev) semantic search, using the **voice-webhook
tool-calling pattern AgentPhone recommends**. AgentPhone handles the
telephony, STT, and TTS; your webhook runs Claude in a tool-call loop with
`moss_search` as the only tool; the grounded reply is streamed back as the
spoken answer.

- [AgentPhone - "Example: tool-calling handler (Python / Flask)"](https://docs.agentphone.ai/documentation/guides/calls)

## Why this is the right shape

Realtime voice models often emit an ungrounded reply before a tool returns.
AgentPhone's webhook-voice mode inverts that: AgentPhone has nothing to
speak until your handler returns text, so the spoken answer is always built
from whatever `moss_search` produced. Tool calling (rather than ambient
retrieval) also lets the model rewrite the user's question into a focused
search query and skip retrieval entirely on small talk.

## What this example does

1. Receives `agent.message` webhooks from AgentPhone.
2. Verifies the `X-Webhook-Signature` HMAC.
3. Streams an immediate interim NDJSON line ("Let me check that for you.").
4. Runs a Claude tool-calling loop: model may call `moss_search(query=...)`,
   we run the search against Moss, the model gets the excerpts back and
   produces the final answer.
5. Streams the final NDJSON line, which ends the spoken turn.

For SMS, MMS, and iMessage the same tool loop runs and the answer is
returned as a single JSON body.

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

`AGENTPHONE_WEBHOOK_SECRET` is the value AgentPhone returns when you create
the webhook (`POST /v1/webhooks`). Without it, every request is rejected
with `401`.

If `MOSS_INDEX_NAME` does not exist yet, the server seeds a small demo
index (refunds, returns, shipping, support hours, password reset) on
startup so you have something to test against.

## Run the server

```bash
uv run python server.py
```

The server listens on `http://localhost:8000/webhook` and `/healthz`.

## Wire it up to AgentPhone

1. Expose the local server publicly. ngrok is the quickest option:
   ```bash
   ngrok http 8000
   ```
2. Register the public URL with AgentPhone:
   ```bash
   curl -X POST https://api.agentphone.ai/v1/webhooks \
     -H "Authorization: Bearer $AGENTPHONE_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://<your-ngrok-host>/webhook", "timeout": 30}'
   ```
   Copy the returned secret into `AGENTPHONE_WEBHOOK_SECRET` and restart
   the server.
3. Create an agent with `voiceMode: "webhook"` and attach a phone number
   (`POST /v1/agents`, then `POST /v1/agents/{id}/numbers`).
4. Call the number, or place a browser test call with
   `POST /v1/calls/web`.

## Run the tests

```bash
uv run python test_integration.py
```

Tests are mocked end to end. They exercise:

- HMAC signature verification (accept valid, reject tampered body and
  garbage signatures).
- Tool-calling loop: model asks for `moss_search`, bridge runs Moss, model
  produces the final answer using the returned excerpts.
- Tool-calling loop: model can answer directly without calling the tool.
- Voice stream: emits the interim filler line followed by the final line.

## How it works

| File | Description |
|------|-------------|
| `moss_agentphone.py` | `MossAgentPhoneBridge` (tool loop) and `verify_webhook_signature` |
| `server.py` | FastAPI app that handles AgentPhone webhooks |
| `test_integration.py` | Mocked unit tests |
| `pyproject.toml` | Package metadata |
| `.env.example` | Template for required environment variables |

### The tool

The model sees one tool:

```python
{
    "name": "moss_search",
    "description": "Search the Moss knowledge base for documents that "
                   "could answer the caller's question...",
    "input_schema": {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
}
```

Each call hits `MossClient.query(index, query, QueryOptions(top_k, alpha))`
and returns a numbered string of excerpts the model can quote from.

### The loop

`MossAgentPhoneBridge.run_tool_call` mirrors AgentPhone's reference
example. `TOOLS` is the schema list, `TOOL_HANDLERS` maps each tool name
to its handler:

```python
for _ in range(self.max_tool_iterations):
    response = await client.messages.create(
        model=self.model,
        tools=TOOLS,
        messages=messages,
        ...
    )
    if response.stop_reason != "tool_use":
        return _extract_text(response)
    # otherwise: run the requested tools via TOOL_HANDLERS,
    # append tool_results, loop
```

The loop is bounded (`max_tool_iterations=5`) so a misbehaving model
cannot stall the call.

### Voice response shape

AgentPhone accepts NDJSON in the voice webhook response. Each line is one
spoken segment:

```
{"text": "Let me check that for you.", "interim": true}
{"text": "Refunds are processed within 3 to 5 business days."}
```

`interim: true` keeps the call open while more lines stream; the final
line (without `interim`) ends the turn.

### Webhook signature

AgentPhone signs `{timestamp}.{raw_body}` with HMAC-SHA256 using the
secret returned from `POST /v1/webhooks`. The headers are:

- `X-Webhook-Signature: sha256=<hex>`
- `X-Webhook-Timestamp: <unix_seconds>`
- `X-Webhook-ID: <unique_delivery_id>` (use for idempotency)
- `X-Webhook-Event: <event_type>`

`verify_webhook_signature` recomputes the digest and uses
`hmac.compare_digest` to avoid timing leaks.

## Notes

- The example uses Anthropic Claude for the LLM hop, matching AgentPhone's
  reference example. Any chat client that exposes a tools-based
  `messages.create`-shaped API works; the `anthropic_client` parameter on
  `MossAgentPhoneBridge` is duck-typed.
- `agent.call_ended` deliveries are acked with `{"ok": true}`. Hook in
  your own logging or evals there if you want a transcript record.

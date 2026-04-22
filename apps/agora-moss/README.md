# agora-moss demo

A runnable end-to-end example of Moss semantic search inside an Agora Conversational AI voice agent, via the `agora-moss` MCP server.

## What this shows

- A minimal FastMCP streamable-HTTP server (`server.py`) exposing `search_knowledge_base`.
- A helper (`start_agent.py`) that mints an RTC token and starts an Agora ConvoAI agent wired to that MCP server, using Deepgram ASR and Cartesia TTS.
- A seeding script (`create_index.py`) that uploads sample docs to a Moss index.

## Prerequisites

- Python 3.10+ and [uv](https://docs.astral.sh/uv/).
- Moss project credentials: `MOSS_PROJECT_ID`, `MOSS_PROJECT_KEY` — sign up and grab them at [moss.dev](https://moss.dev).
- An Agora account with Conversational AI enabled: `AGORA_APP_ID`, `AGORA_APP_CERTIFICATE`, `AGORA_CUSTOMER_ID`, `AGORA_CUSTOMER_SECRET`.
- Deepgram + Cartesia API keys (or swap to any other vendors Agora ConvoAI supports).
- An LLM endpoint that speaks OpenAI-compatible `/chat/completions` streaming (e.g. OpenAI, Groq, Together, vLLM).
- `ngrok` (or any other public-URL tunnel) for local dev so Agora can reach your MCP server.

## Setup

```bash
cd apps/agora-moss
cp env.example .env
# edit .env and fill in credentials
uv sync --dev
```

## Seed the demo index

```bash
uv run python create_index.py
```

This uploads `moss_docs.json` to `$MOSS_INDEX_NAME`.

## Run the MCP server

```bash
uv run uvicorn server:app --host 0.0.0.0 --port 8080
```

The MCP endpoint is served at `http://127.0.0.1:8080/mcp`. Expose it publicly with:

```bash
ngrok http 8080
# → https://<random>.ngrok.io/mcp
```

Put the public URL in your `.env` as `AGORA_MCP_PUBLIC_URL`.

## Start the Agora agent

In another terminal:

```bash
uv run python start_agent.py
```

This prints the started agent's ID on success. Use Agora's web demo (or your own RTC client) to join `$AGORA_CHANNEL` — when you speak, the ConvoAI LLM can now call `search_knowledge_base` against your Moss index.

## Docker

```bash
# from repo root
docker build -t agora-moss:local -f apps/agora-moss/Dockerfile .
docker run --rm -p 8080:8080 --env-file apps/agora-moss/.env agora-moss:local
```

The published image is `ghcr.io/usemoss/agora-moss`.

## Integrating into your own ConvoAI setup

If you already have an Agora ConvoAI agent, you only need to append two things to your existing `join` body — no changes to vendor, LLM URL, or any other config:

```json
{
  "properties": {
    "llm": {
      "mcp_servers": [{
        "name": "moss",
        "endpoint": "https://<your-mcp-host>/mcp",
        "transport": "streamable_http",
        "allowed_tools": ["search_knowledge_base"],
        "headers": { "Authorization": "Bearer <optional>" }
      }]
    },
    "advanced_features": { "enable_tools": true }
  }
}
```

Agora rule to watch: the MCP server entry's `name` must be ≤48 chars, alphanumeric only — no hyphens or underscores.

## License

BSD-2-Clause. See repository root.

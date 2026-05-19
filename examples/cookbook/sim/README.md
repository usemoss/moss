# Moss + sim.ai

Give your [sim.ai](https://sim.ai/) workflows instant retrieval with [Moss](https://docs.moss.dev) — a real-time semantic search runtime that runs on-device at sub-10ms latency. sim.ai calls it via a lightweight FastAPI webhook server whenever a workflow node needs to retrieve context.

## How it works

```
sim.ai workflow
  └─ HTTP tool node  POST /search {"query": "..."}
       └─ server.py (FastAPI)
            └─ MossSimSearch  ──▶  Moss index (on-device, <10ms)
                 └─ {"results": [...], "time_taken_ms": 4}
```

## Prerequisites

- [Moss Portal](https://portal.usemoss.dev) project with credentials
- sim.ai workspace with a deployed workflow
- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

## Setup

### 1. Install dependencies

```bash
cd examples/cookbook/sim
uv sync
```

### 2. Configure environment

```bash
cp .env.example .env
# fill in MOSS_PROJECT_ID, MOSS_PROJECT_KEY
```

### 3. Index your documents

Put `.txt` or `.md` files in a `docs/` directory, then run:

```bash
uv run python example_index.py --docs ./docs
```

### 4. Start the webhook server

```bash
uv run uvicorn server:app --host 0.0.0.0 --port 8000
```

The server pre-loads the Moss index on startup. Check `/health` to confirm readiness.

### 5. Add the tool to your sim.ai workflow

In your sim.ai workflow editor, add an **HTTP tool** node:

| Field | Value |
|-------|-------|
| Method | `POST` |
| URL | `https://your-server.com/search` |
| Body | `{"query": "{{user_message}}"}` |

Map the response: `results[*].content` → injected into the LLM context block.

## API

### `POST /search`

**Request**
```json
{"query": "how do I reset my password?"}
```

**Response**
```json
{
  "results": [
    {"content": "To reset your password...", "score": 0.94, "source": "faq.md"},
    {"content": "Account recovery steps...", "score": 0.87, "source": "help.md"}
  ],
  "time_taken_ms": 4
}
```

### `GET /health`

Returns `{"status": "ok", "index_loaded": true}` once the index is warm.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MOSS_PROJECT_ID` | — | Moss project ID (required) |
| `MOSS_PROJECT_KEY` | — | Moss project key (required) |
| `MOSS_INDEX_NAME` | `sim-docs` | Moss index to query |
| `MOSS_TOP_K` | `5` | Results returned per query |

## Deploying

The server is a standard ASGI app and can be deployed anywhere you'd run a FastAPI service.
For local testing with a public URL, use [ngrok](https://ngrok.com/):

```bash
ngrok http 8000
# paste the https:// URL into your sim.ai workflow's HTTP tool node
```

## License

[BSD 2-Clause](../../../packages/sim-moss/LICENSE)

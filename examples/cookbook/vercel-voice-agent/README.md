# MOSS Voice Agent — Vercel AI Gateway

Realtime voice agent using [Vercel AI Gateway](https://vercel.com/blog/realtime-voice-agents-on-ai-gateway) with MOSS as the knowledge base. Speak a question — the agent searches your MOSS index and answers out loud.

## Architecture

```text
Browser (useRealtime) ──WebSocket── Vercel AI Gateway ── gpt-realtime-2
        │                                   │
        │   tool call: search_knowledge_base │
        └─── POST /api/token ───────────────►│
                                         MOSS index (local)
```

- `POST /api/token` (empty body) — mints a short-lived WebSocket token via the gateway
- `POST /api/token` (`{ query }`) — executes MOSS search; uses local in-memory index loaded at startup

> **Security note:** `/api/token` is unauthenticated only when `ALLOW_UNAUTHENTICATED_DEMO=true` is set (demo). Before deploying publicly, add a session/cookie check so arbitrary callers cannot mint Gateway tokens or query your index.

## Setup

### 1. Install dependencies

Requires **Node.js ≥ 22** (`ai@7` and `@ai-sdk/gateway@4` require it).

```bash
npm install
```

### 2. Add credentials

```bash
cp .env.example .env
```

| Variable | Where to get it |
| --- | --- |
| `MOSS_PROJECT_ID` | [moss.dev](https://moss.dev) dashboard |
| `MOSS_PROJECT_KEY` | [moss.dev](https://moss.dev) dashboard |
| `MOSS_INDEX_NAME` | Name of the index to search |
| `AI_GATEWAY_API_KEY` | [Vercel AI Gateway](https://vercel.com/dashboard/ai-gateway) → API Keys |

### 3. Run

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) and tap the orb to start talking.

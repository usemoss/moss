# MOSS + Vercel AI Gateway Voice Agent

Realtime voice agent using [Vercel AI Gateway](https://vercel.com/blog/realtime-voice-agents-on-ai-gateway) with MOSS as the knowledge base. Speak a question — the agent searches your MOSS index and answers out loud.

## How it works

```text
Browser (useRealtime)  ──WebSocket──  Vercel AI Gateway  ──  gpt-realtime-2
       │                                      │
       │  tool call: search_knowledge_base    │
       └──── POST /api/token ────────────────►│
                                          MOSS index
```

- `POST /api/token` (empty body) — generates a short-lived WebSocket token (keeps API keys off the client)
- `POST /api/token` (with `{ query }`) — executes MOSS search when the model calls `search_knowledge_base`

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

Fill in `.env`:

| Variable | Where to get it |
| --- | --- |
| `MOSS_PROJECT_ID` | [moss.dev](https://moss.dev) dashboard |
| `MOSS_PROJECT_KEY` | [moss.dev](https://moss.dev) dashboard |
| `MOSS_INDEX_NAME` | Name of the index to search |
| `AI_GATEWAY_API_KEY` | [Vercel AI Gateway](https://vercel.com/dashboard/ai-gateway) → API Keys |
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com) |

### 3. Run

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000), click **Start talking**, and ask anything covered by your index.

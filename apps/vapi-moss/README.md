# VAPI + Moss: Custom Tool Webhook Server

A webhook server that connects [VAPI](https://vapi.ai/) voice agents to [Moss](https://www.moss.dev/) semantic search via a Custom Tool. The LLM decides when to search and refines the query before sending it, resulting in better retrieval quality.

## Architecture

```
User speaks → VAPI STT → LLM refines query → tool-calls request → This server → Moss query (sub-10ms) → Results returned → LLM synthesizes answer → TTS
```

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [ngrok](https://ngrok.com/) (for exposing localhost to VAPI)
- API keys:
  - [Moss](https://portal.usemoss.dev) — semantic retrieval
  - [VAPI](https://vapi.ai/) — voice agent platform

## Quick Start

1. **Configure environment:**

   ```bash
   cp env.example .env
   # Edit .env and fill in your Moss credentials
   ```

2. **Start the server:**

   ```bash
   uv run uvicorn server:app --port 3001
   ```

4. **Expose with ngrok** (separate terminal):

   ```bash
   ngrok http 3001
   ```

5. **Create a VAPI assistant with the Moss tool:**

   ```bash
   curl -X POST https://api.vapi.ai/assistant \
     -H "Authorization: Bearer $VAPI_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Moss Support Agent",
       "model": {
         "provider": "openai",
         "model": "gpt-4o",
         "messages": [
           {
             "role": "system",
             "content": "You are a helpful customer support agent. Use the search_knowledge tool to look up answers before responding."
           }
         ],
         "tools": [
           {
             "type": "function",
             "function": {
               "name": "search_knowledge",
               "description": "Search the knowledge base for relevant information. Refine the user question into a clear search query.",
               "parameters": {
                 "type": "object",
                 "properties": {
                   "query": {
                     "type": "string",
                     "description": "The search query to find relevant knowledge base articles"
                   }
                 },
                 "required": ["query"]
               }
             },
             "server": {
               "url": "https://YOUR_NGROK_URL/tool/search"
             }
           }
         ]
       }
     }'
   ```

6. **Test it** — call the assistant via VAPI dashboard or API.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MOSS_PROJECT_ID` | — | Moss project ID |
| `MOSS_PROJECT_KEY` | — | Moss project key |
| `MOSS_INDEX_NAME` | — | Moss index to query |
| `VAPI_WEBHOOK_SECRET` | — | Webhook secret for signature verification (leave empty to disable) |

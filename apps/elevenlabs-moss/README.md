# ElevenLabs + Moss

Give your ElevenLabs voice agent a knowledge base powered by Moss semantic search. Queries run locally in <10ms after the index is loaded.

```
Microphone → ElevenLabs (STT → LLM → TTS) → Speaker
                    ↕ tool call
              Moss Search (<10ms local)
```

## 1. Set Up ElevenLabs

1. Go to [elevenlabs.io](https://elevenlabs.io) → **Conversational AI** → **Create Agent**
2. Set the **First message** to:
   ```
   Hey! How can I help you today?
   ```
3. Set the **System prompt** to:
   ```
   You are a customer support voice agent for an online store.

   ## Rules

   - NEVER say "let me look that up", "let me check", or "let me search." Just answer.
   - Call search_knowledge_base before every answer but never mention it.
   - Keep responses under 2 sentences. This is a voice call.
   - Be confident. Say "Your return window is 30 days" not "I think it might be."
   - Only say you don't know if the question is completely unrelated to orders,
     shipping, returns, billing, or accounts.

   ## Style

   - Warm, natural, concise. No lists. No topic rundowns.
   - Never describe what you can help with unless asked.

   ## Cannot Do

   - Never invent order numbers, tracking numbers, or account details.
   - Never process payments or make account changes — direct to self-service
     or human support.
   ```

4. Go to the **Tools** tab and click **Add tool** → **Client Tool**:

   | Setting | Value |
   |---------|-------|
   | Name | `search_knowledge_base` |
   | Description | `Search the knowledge base for answers to customer questions` |
   | Wait for response | **ON** |
   | Pre-tool speech | Auto |
   | Execution mode | Immediate |
   | Response timeout | 1 second |

   Add one parameter:

   | Field | Value |
   |-------|-------|
   | Data type | String |
   | Identifier | `query` |
   | Required | Yes |
   | Value Type | LLM Prompt |
   | Description | `The customer's question` |

5. Click **Publish**
6. Copy the **Agent ID** from the URL: `elevenlabs.io/app/conversational-ai/agents/<AGENT_ID>`

## 2. Set Up Moss

1. Go to [portal.usemoss.dev](https://portal.usemoss.dev) and create a project
2. Create an index and add your FAQ documents
3. Copy your **Project ID**, **Project Key**, and **Index Name**

## 3. Connect Moss to ElevenLabs

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- `portaudio` system library:
  - macOS: `brew install portaudio`
  - Linux: `sudo apt install portaudio19-dev`

### Install and run

```bash
# Configure credentials
cp env.example .env
# Fill in MOSS_PROJECT_ID, MOSS_PROJECT_KEY, MOSS_INDEX_NAME,
# ELEVENLABS_API_KEY, and ELEVENLABS_AGENT_ID

# Run the bot
uv run elevenlabs_bot.py
```

Speak into your microphone. The agent searches Moss on every question and answers using the results.

## How It Works

1. On startup, the bot downloads the Moss index into memory for local querying
2. It registers a `search_knowledge_base` client tool over the ElevenLabs websocket
3. When you speak, ElevenLabs transcribes your audio and sends it to the LLM
4. The LLM calls `search_knowledge_base` — the bot queries Moss locally (<10ms) and returns results
5. The LLM uses those results to generate a grounded response
6. ElevenLabs converts the response to speech

## Environment Variables

| Variable | Description |
|----------|-------------|
| `MOSS_PROJECT_ID` | Moss project ID from [portal.usemoss.dev](https://portal.usemoss.dev) |
| `MOSS_PROJECT_KEY` | Moss project key |
| `MOSS_INDEX_NAME` | Name of the Moss index to query |
| `ELEVENLABS_API_KEY` | ElevenLabs API key from [elevenlabs.io](https://elevenlabs.io) |
| `ELEVENLABS_AGENT_ID` | Agent ID from the ElevenLabs dashboard URL |

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `No module named 'pyaudio'` | Install `portaudio` first: `brew install portaudio` (macOS) |
| Tool never called (no Moss logs) | Verify the tool is attached to the agent in the Tools tab and the name is exactly `search_knowledge_base` |
| 100% tool error rate | Do not pass a custom event loop to `ClientTools()` — let it create its own thread |
| Agent says "I don't have that info" | The tool isn't wired up in the dashboard, or the search returned no results for that query |
| Agent says "let me look that up" | Add the "NEVER say let me look that up" rule to the system prompt |
| Microphone not working | Allow mic access when prompted. Check your default audio input device |

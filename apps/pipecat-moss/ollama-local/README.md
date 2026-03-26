# Ollama + Moss + Pipecat: Local LLM Voice Agent

A voice AI agent with local LLM inference via Ollama, Moss semantic retrieval for RAG, and Pipecat for real-time audio. One `docker compose up` to run the stack.

## Architecture

```
Microphone → Daily/WebRTC → Deepgram STT → Moss Retrieval → Ollama LLM → Cartesia TTS → Speaker
```

| Component | Provider | Local/Cloud |
|-----------|----------|-------------|
| LLM | Ollama (llama3.2) | Local (Docker) |
| Retrieval | Moss | Cloud index mgmt, local query |
| STT | Deepgram | Cloud (free tier) |
| TTS | Cartesia | Cloud (free tier) |
| VAD | Silero | Local |
| Transport | WebRTC (default) | Local |

## Prerequisites

- [Docker](https://www.docker.com/) and Docker Compose
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (for one-time index setup)
- API keys (all have free tiers):
  - [Moss](https://portal.usemoss.dev) — semantic retrieval
  - [Deepgram](https://console.deepgram.com/signup) — speech-to-text
  - [Cartesia](https://play.cartesia.ai/sign-up) — text-to-speech

## Quick Start

1. **Configure environment:**

   ```bash
   cp env.example .env
   # Edit .env and fill in your Moss, Deepgram, and Cartesia keys
   ```

2. **Create the Moss index** (one-time, only needs Moss keys):

   ```bash
   uv run ollama_create_index.py
   ```

3. **Start the stack:**

   ```bash
   docker compose up
   ```

   This will:
   - Start Ollama
   - Pull the `llama3.2` model (first run only, ~2GB)
   - Start the Pipecat bot

4. **Open http://localhost:7860** and click Connect.

> First run may take a few minutes while the Ollama model downloads. Subsequent runs start in seconds.

## Running Without Docker

If you prefer running directly on your machine:

1. Install and start Ollama:

   ```bash
   ollama serve
   ollama pull llama3.2
   ```

2. Install dependencies:

   ```bash
   uv sync
   ```

3. Set the Ollama URL for local access:

   ```bash
   export OLLAMA_BASE_URL=http://localhost:11434/v1
   ```

4. Run the bot:

   ```bash
   uv run ollama_bot.py
   ```

5. Open http://localhost:7860 and click Connect.

## Using Daily Transport (Optional)

The default transport is local WebRTC (no API key needed). To use Daily instead:

1. Get a free API key from [daily.co](https://dashboard.daily.co/u/signup)
2. Add to your `.env`:

   ```ini
   DAILY_API_KEY=your_daily_api_key
   ```

3. Run with the Daily flag:

   ```bash
   uv run ollama_bot.py -t daily
   ```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_MODEL` | `llama3.2` | Ollama model to use |
| `OLLAMA_BASE_URL` | `http://ollama:11434/v1` | Ollama API endpoint |
| `MOSS_TOP_K` | `5` | Number of passages to retrieve |

## GPU Acceleration

For faster inference with an NVIDIA GPU, uncomment the GPU section in `docker-compose.yml`:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

## Troubleshooting

- **Bot fails to start:** Check `docker compose logs ollama-init` to see if the model pull succeeded.
- **Slow responses:** Running on CPU is functional but slower. Use a smaller model (`OLLAMA_MODEL=llama3.2:1b`) or enable GPU passthrough.
- **Model not found:** The `ollama-init` service auto-pulls on first run. If it failed, run `docker compose exec ollama ollama pull llama3.2` manually.
- **Browser permissions:** Allow microphone access when prompted.
- **Connection issues:** Try a different browser or check VPN/firewall settings.

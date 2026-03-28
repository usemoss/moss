# Ollama + Moss + Pipecat + TADA MLX: Fully Local Voice Agent

A voice AI agent with local LLM inference via Ollama, Moss semantic retrieval for RAG, Hume AI's TADA (MLX) for fully local TTS on Apple Silicon, and Pipecat for real-time audio.

## Architecture

```
Microphone → Daily/WebRTC → Deepgram STT → Moss Retrieval → Ollama LLM → TADA MLX TTS → Speaker
```

| Component | Provider | Local/Cloud |
|-----------|----------|-------------|
| LLM | Ollama (llama3.2) | Local |
| Retrieval | Moss | Cloud index mgmt, local query |
| STT | Deepgram | Cloud (free tier) |
| TTS | TADA MLX (Hume AI) | Local (Apple Silicon) |
| VAD | Silero | Local |
| Transport | WebRTC (default) | Local |

## Prerequisites

- Apple Silicon Mac (M1/M2/M3/M4)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager
- [HuggingFace account](https://huggingface.co) with Llama 3.2 license accepted
- API keys:
  - [Moss](https://portal.usemoss.dev) — semantic retrieval
  - [Deepgram](https://console.deepgram.com/signup) — speech-to-text
- A 10-second voice reference WAV file (for TADA voice cloning)

## Quick Start

1. **Configure environment:**

   ```bash
   cp env.example .env
   # Edit .env and fill in your Moss and Deepgram keys (TADA runs locally, no key needed)
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

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_MODEL` | `llama3.2` | Ollama model to use |
| `OLLAMA_BASE_URL` | `http://ollama:11434/v1` | Ollama API endpoint |
| `MOSS_TOP_K` | `5` | Number of passages to retrieve |

## TADA MLX Voice

This example uses Hume AI's open-source [TADA](https://github.com/HumeAI/tada) model running locally via MLX on Apple Silicon. TADA is a voice-cloning TTS — it requires a ~10 second reference WAV file to define the voice.

Place your reference audio at `reference_voice.wav` in this directory. Configure via env vars:

| Variable | Default | Description |
|----------|---------|-------------|
| `TADA_MODEL_ID` | `HumeAI/mlx-tada-1b` | HuggingFace model ID |
| `TADA_QUANTIZE` | `4` | Quantization bits (4 = fastest, ~3GB RAM) |

**First run**: The model (~4GB) downloads from HuggingFace automatically. Subsequent runs use the cache.

## GPU Acceleration

Ollama automatically detects and uses available GPU hardware. No configuration needed when running natively — just install Ollama and it uses your GPU.

### NVIDIA (CUDA)

When using Docker, uncomment the GPU section in `docker-compose.yml`:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

Requires the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).

### Apple Silicon (Metal)

Runs natively with Metal acceleration — no Docker needed. Install Ollama directly:

```bash
brew install --cask ollama
```

### CPU-Only Fallback

No GPU? Use a smaller model for faster responses:

```ini
OLLAMA_MODEL=llama3.2:1b
```

## Troubleshooting

- **Bot fails to start:** Check `docker compose logs ollama-init` to see if the model pull succeeded.
- **Slow responses:** Enable GPU acceleration (see above) or use a smaller model (`OLLAMA_MODEL=llama3.2:1b`).
- **Model not found:** The `ollama-init` service auto-pulls on first run. If it failed, run `docker compose exec ollama ollama pull llama3.2` manually.
- **Browser permissions:** Allow microphone access when prompted.
- **Connection issues:** Try a different browser or check VPN/firewall settings.

# Voice Agent

A voice assistant that answers questions using your Moss knowledge base. You talk to it, it searches your data, and responds out loud.

## What you need

- A [Moss](https://moss.dev) account with a project and an index loaded with your data
- A [LiveKit](https://livekit.io) account (or run it locally)
- An [OpenAI](https://platform.openai.com) API key (for the AI responses)
- A [Deepgram](https://deepgram.com) API key (for speech-to-text)
- A [Cartesia](https://play.cartesia.ai) API key (for text-to-speech)

## Setup

1. Install dependencies:

   ```bash
   uv sync
   ```

2. Copy the env file and fill in your keys:

   ```bash
   cp .env.example .env
   ```

   Open `.env` and add:

   ```env
   LIVEKIT_URL=ws://localhost:7880
   LIVEKIT_API_KEY=devkey
   LIVEKIT_API_SECRET=secret

   MOSS_PROJECT_ID=your-project-id
   MOSS_PROJECT_KEY=your-project-key
   MOSS_INDEX_NAME=your-index-name

   OPENAI_API_KEY=...
   DEEPGRAM_API_KEY=...
   CARTESIA_API_KEY=...
   ```

3. Download the required model files:

   ```bash
   python agent.py download-files
   ```

## Run

```bash
python agent.py console
```

Speak into your microphone and the agent responds out loud.

## Resources

- [Docs](https://docs.moss.dev/?utm_source=github&utm_medium=readme&utm_campaign=voice-agent)
- [Portal](https://portal.usemoss.dev/?utm_source=github&utm_medium=readme&utm_campaign=voice-agent)
- [GitHub](https://github.com/usemoss/moss)
- [Discord](https://discord.com/invite/eMXExuafBR?utm_source=github&utm_medium=readme&utm_campaign=voice-agent)

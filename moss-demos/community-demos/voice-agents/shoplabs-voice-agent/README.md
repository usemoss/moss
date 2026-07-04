# Shoplabs Voice Agent Demo

This community demo is a voice-based ecommerce support assistant inspired by the kind of problems Shoplabs solves for D2C brands.

The agent can answer questions about:

- refunds and returns
- shipping times and order tracking
- password resets and account support
- product recommendations
- checkout hesitation and abandoned cart objections

It uses Moss retrieval to ground the voice assistant in a small ecommerce knowledge base before the LLM answers.

## How to run locally

1. Install dependencies:

```bash
cd moss-live-labs/community-demos/voice-agents/shoplabs-voice-agent
uv sync
```

This demo is configured for the Pipecat WebRTC transport. The Daily and local Silero/VAD extras were removed so the dependencies install cleanly on Windows without pulling large local-model packages.

2. Create a `.env` file:

```bash
cp .env.example .env
```

3. Fill in these environment variables:

```ini
MOSS_PROJECT_ID=your_moss_project_id
MOSS_PROJECT_KEY=your_moss_project_key
MOSS_INDEX_NAME=shoplabs-demo-faq

DEEPGRAM_API_KEY=your_deepgram_api_key
GOOGLE_API_KEY=your_google_api_key
CARTESIA_API_KEY=your_cartesia_api_key

GEMINI_MODEL=gemini-2.5-flash
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
MOSS_TOP_K=5
```

`GEMINI_API_KEY` also works if you prefer that env var name; `bot.py` accepts either.

4. Create the demo Moss index:

```bash
uv run python create_index.py
```

5. Run the voice bot:

```bash
uv run python bot.py
```

6. Open the local Pipecat interface shown in the terminal and talk to the agent.

## Suggested demo questions

- What is your refund policy?
- How do I track my order?
- I forgot my password, what should I do?
- Which product is better for dry skin?
- I left checkout because shipping was too expensive.

## Moss SDK methods used and why

- `create_index()` in `create_index.py`
  Creates a demo retrieval index with ecommerce FAQs and product guidance.

- `load_index()` in `bot.py`
  Preloads the index for low-latency retrieval during voice conversations.

- `query()` via `MossRetrievalService.query(...)` in `bot.py`
  Retrieves the most relevant support and product documents before the LLM responds.

## Notes

- This demo is intentionally small and optimized for a Live Lab walkthrough.
- The voice loop is Pipecat + Deepgram + Gemini + Cartesia, with Moss providing retrieval.
- Gemini is called through Google's OpenAI-compatible endpoint configured by `GEMINI_BASE_URL`.

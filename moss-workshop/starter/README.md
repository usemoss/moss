# Moss Hackathon Starter

A real-time voice agent grounded in Moss - the hack-day helper, and a head start for
your own build. For **Agents Hack Day at Bright Data** (July 18, 2026).

## Run it

```bash
# 1. Clone the Moss repo and enter the starter
git clone https://github.com/usemoss/moss
cd moss/moss-workshop/starter

# 2. Install (Python 3.10+)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Add your keys
cp .env.example .env
#    then edit .env:
#    MOSS_PROJECT_ID, MOSS_PROJECT_KEY   <- from https://portal.usemoss.dev
#    LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
#    OPENAI_API_KEY, DEEPGRAM_API_KEY

# 4. Create the FAQ index in Moss (run once)
python build_index.py

# 5. Talk to the agent
python voice_agent.py console
```

## How it works

LiveKit runs the audio (STT / LLM / TTS); Moss is the retrieval. The agent uses both
Moss primitives: the FAQ **cloud index** (long-term knowledge) and a live **session**
that indexes each turn so it can recall the conversation. Both query in-process, under
10 ms. Edit `data/hackathon_faq.json`, or point it at your own data - e.g. live web data
pulled with Bright Data - to build your own agent.

## Docs
https://docs.moss.dev · Discord: https://discord.gg/eMXExuafBR

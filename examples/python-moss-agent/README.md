# Ecommerce Support Voice Agent

End-to-end LiveKit voice agent built on the
[`moss-agent`](https://github.com/usemoss/moss/tree/main/python/moss-agent)
SDK. Showcases the **prewarm-once, attach-per-room** pattern: one
process-wide `MossAgent` with hot indexes loaded at boot, every concurrent
room queries the same warm in-process cache via a one-line
`agent.attach(ctx)`.

```
prewarm() runs ONCE per worker process
   |
   +-- MossAgent(project_id, project_key)
   +-- agent.load_indexes(["ecommerce_products",
                           "ecommerce_faq",
                           "ecommerce_policies"])

handle_visit(ctx) runs PER LiveKit room
   |
   +-- await ctx.connect()
   +-- call = agent.attach(ctx)        # one line, scoped to this room
   +-- AgentSession(...).start(...)
   +-- function_tools route every query through `call.query_multi_index(...)`
```

The result: indexes are loaded once at boot, served sub-10ms to hundreds
of concurrent rooms.

## What this example demonstrates

| Capability | Where to look |
|---|---|
| Process-wide `MossAgent` + `load_indexes` in `prewarm` | `agent.py` — `prewarm()` |
| Per-room `MossCall` scope via `attach(ctx)` | `agent.py` — `handle_visit()` |
| Multi-index query across three KBs in one call | `agent.py` — `search_store` tool |
| Single-index query (when you know the scope) | `agent.py` — `search_products` tool |
| Three-index ingestion script | `create_indexes.py` |

## Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (or `pip` + `venv`)
- A [Moss](https://moss.dev) project (`MOSS_PROJECT_ID`, `MOSS_PROJECT_KEY`)
- API keys for:
  - [OpenAI](https://platform.openai.com) — LLM
  - [Deepgram](https://deepgram.com) — speech-to-text
  - [Cartesia](https://play.cartesia.ai) — text-to-speech
- For browser testing only: a [LiveKit](https://livekit.io) project (cloud
  or `livekit-server --dev` locally). **Not required for console mode.**

## Setup

1. **Install dependencies**

   ```bash
   uv sync
   ```

2. **Configure environment**

   ```bash
   cp .env.example .env
   ```

   Fill in your Moss credentials and provider keys.

3. **Build the Moss indexes**

   ```bash
   uv run python create_indexes.py
   ```

   This creates three indexes — `ecommerce_products`, `ecommerce_faq`,
   `ecommerce_policies` — from the JSON files in `data/`. Edit those
   files to swap in your own catalog, FAQ, or policy text; no code
   changes needed.

4. **Run the agent**

   ```bash
   uv run python agent.py console
   ```

   The agent grabs your mic and speakers directly. Press `Ctrl+C` to stop.

## Try this conversation

```text
Customer: Hi, what are the Aurora Pro headphones like?
Agent:    [search_products] The Aurora Pro is a wireless over-ear with
          active noise cancellation, 40-hour battery, USB-C fast charge,
          Bluetooth 5.3, and multipoint pairing. It's $279, and comes in
          midnight black, sand, and sage.

Customer: And how long does shipping take?
Agent:    [search_store] Standard shipping is free over $50 in the US and
          takes 3 to 5 business days. Expedited 2-day is $12, overnight is
          $25 if you order before 2pm Eastern.

Customer: Can I return them if I don't like them?
Agent:    [search_store] Yes — 60 days from delivery, free return shipping
          via our prepaid label. Original shipping isn't refundable but
          everything else hits your card within 5 business days of the
          return being scanned.
```

Notice the agent uses `search_products` for the first question (clearly
product-scoped) and `search_store` for the next two (broader, the
multi-index search picks the right docs from FAQ vs. policies).

## Files

```text
python-moss-agent/
├── agent.py            # Voice agent — prewarm + attach + tools
├── create_indexes.py   # Read data/*.json, build three Moss indexes
├── data/
│   ├── product_catalog.json   # 10 products
│   ├── faq.json               # 8 FAQ entries
│   └── policies.json          # 7 policy docs
├── pyproject.toml      # uv-managed dependencies
├── .env.example        # Required environment variables
└── README.md           # This file
```

## Resources

- [Moss docs](https://docs.moss.dev)
- [Moss llms.txt](https://moss.dev/llms.txt)
- [LiveKit Agents docs](https://docs.livekit.io/agents/)
- [Discord](https://moss.link/discord)

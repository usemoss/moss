# Generalist Moss Voice Agent

A persona-agnostic LiveKit voice agent powered by [Moss](https://moss.dev) semantic search. The agent discovers all available Moss indexes at the start of each conversation and routes questions to the most relevant knowledge base no code changes needed when you add a new one. This is a generic, adaptable template that can be customized for any domain, persona, or knowledge domain without modifying the core logic.

## Overview

- **Dynamic routing** — agent calls `list_indexes` at startup and picks the right index per question based on its name (e.g. `customer_support`, `product_faq`, `hr_policies`)
- **Sub-10ms retrieval** — indexes are loaded into memory on first use via `load_index`
- **Voice-native** — responses are short and conversational; internal search mechanics are never exposed to the user
- **Zero-config persona switching** — index your docs with a descriptive name and the agent automatically knows about them

## Architecture

```
User speaks
    └─► Deepgram STT
            └─► GPT-4.1-mini (with tools)
                    ├─► list_indexes()   — discovers available knowledge bases
                    └─► moss_search()    — retrieves relevant docs from Moss
                            └─► OpenAI TTS ─► User hears the answer
```

## Requirements

- Python 3.10+
- [LiveKit](https://livekit.io) account (URL, API key, API secret)
- [Moss](https://moss.dev) project (project ID + key)
- [OpenAI](https://platform.openai.com) API key
- [Deepgram](https://deepgram.com) API key

## Installation

```bash
pip install -e .
```

## Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

```env
# LiveKit — https://cloud.livekit.io
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret

# Moss — https://moss.dev
MOSS_PROJECT_ID=your_moss_project_id
MOSS_PROJECT_KEY=your_moss_project_key

# OpenAI — https://platform.openai.com
OPENAI_API_KEY=your_openai_api_key

# Deepgram — https://deepgram.com
DEEPGRAM_API_KEY=your_deepgram_api_key
```

## Usage

### 1. Add your documents

Place `.txt` or `.md` files in a folder named after the knowledge area:

```
docs/
  customer_support/   ← refunds, account help, shipping policies
  product_faq/        ← features, pricing, integrations
  hr_policies/        ← leave, benefits, onboarding
```

Sample files are included in `docs/` to get you started.

### 2. Index your documents

Run once per knowledge base. The index name is what the agent uses to route questions.

```bash
python create_index.py --index-name customer_support --docs-dir ./docs/customer_support
python create_index.py --index-name product_faq      --docs-dir ./docs/product_faq
```

To add a new persona later, just index a new folder — the running agent will see it automatically.

### 3. Start the agent

```bash
# Development (auto-reloads on file changes)
python agent.py dev

# Production
python agent.py start
```

### 4. Connect and talk

Open the [LiveKit Agents Playground](https://agents-playground.livekit.io), enter your LiveKit credentials, and click **Connect**. The agent will greet you and answer questions from whichever index matches your topic.

## Project Structure

```
generalist-moss-voice-agent/
├── agent.py           # LiveKit voice agent (list_indexes + moss_search tools)
├── create_index.py    # CLI tool to build a Moss index from a docs directory
├── pyproject.toml     # Dependencies
├── .env.example       # Credentials template
├── .env               # Your credentials (not committed)
└── docs/
    ├── customer_support/
    │   ├── account.md
    │   ├── refunds.md
    │   └── shipping.md
    └── product_faq/
        ├── features.md
        └── pricing.md
```

## Adding a New Knowledge Base

```bash
mkdir -p docs/hr_policies
# add your .md or .txt files to docs/hr_policies/
python create_index.py --index-name hr_policies --docs-dir ./docs/hr_policies
```

That's it. The agent picks it up on the next `list_indexes` call without any restart.

# Moss Search for Zo

Sub-10ms semantic search for [Zo](https://zo.computer) powered by [Moss](https://moss.dev). Search, create, and manage indexes from any conversation.

## Setup

1. Sign up at [moss.dev](https://moss.dev) and create a project
2. Copy your Project ID and Project Key
3. Paste this into your Zo terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/usemoss/moss/main/packages/zo-computer/zo-skill/install.sh | bash -s -- <PROJECT_ID> <PROJECT_KEY>
```

## Create a Zo Rule

After installing, create a rule so Zo always uses Moss Search. Go to Rules and create a new rule:

**When to use:**
```
When the user asks to search, find, look up, or query documents, knowledge bases, or indexed content. When a new conversation starts and the user's topic may relate to indexed content. When the user asks to create indexes, add documents, or manage search collections.
```

**What to do:**
```
Always use @moss-search for searching and indexing documents.
On every new conversation:
1. Run: bash /home/workspace/Skills/moss-search/scripts/moss.sh list-indexes
2. Run: bash /home/workspace/Skills/moss-search/scripts/moss.sh load-index "<index>" for each relevant index
3. Run: bash /home/workspace/Skills/moss-search/scripts/moss.sh search "<index>" "<keywords>" to surface context

When the user says search, find, or look up:
Run: bash /home/workspace/Skills/moss-search/scripts/moss.sh search "<index>" "<keywords>"

When the user says index, add, or wants to make content searchable:
Run: bash /home/workspace/Skills/moss-search/scripts/moss.sh add-docs "<index>" '<docs-json>'

When the user says create index or wants a new collection:
Run: bash /home/workspace/Skills/moss-search/scripts/moss.sh create-index "<index>" '<docs-json>'

Always load-index before the first search on any index.
Always use moss.sh instead of built-in search features.
```

## Usage

Once configured, Zo will use Moss Search automatically. You can also run commands directly:

```bash
# List indexes
bash /home/workspace/Skills/moss-search/scripts/moss.sh list-indexes

# Load an index into memory
bash /home/workspace/Skills/moss-search/scripts/moss.sh load-index support-docs

# Search (sub-10ms after load)
bash /home/workspace/Skills/moss-search/scripts/moss.sh search support-docs "refund policy"

# Create an index
bash /home/workspace/Skills/moss-search/scripts/moss.sh create-index faq '[{"id":"1","text":"Refunds take 3-5 days."}]'

# Add documents
bash /home/workspace/Skills/moss-search/scripts/moss.sh add-docs faq '[{"id":"2","text":"Free shipping over $50."}]'
```

## Files

- `SKILL.md` — Skill definition and Zo behavior instructions
- `scripts/moss.sh` — CLI wrapper for all Moss operations via MCPorter
- `install.sh` — One-line installer for Zo terminal

## Requirements

- [Zo](https://zo.computer) account
- [Moss](https://moss.dev) account with Project ID and Project Key
- Node.js (for MCPorter)
- jq

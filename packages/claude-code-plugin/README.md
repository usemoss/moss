# claude-moss

Moss semantic search plugin for Claude Code. Auto-injects relevant context from your Moss indexes on every prompt, captures conversations as searchable memory, and provides tools for index management.

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- Node.js 18+
- A Moss account with a project key — sign up at [moss.dev](https://moss.dev)

## Setup

1. Go to [moss.dev](https://moss.dev) and create an account
2. Create a project and grab your **Project ID** and **Project Key**
3. Create an index and add your documents (code, docs, runbooks, etc.)

## Installation

```bash
# 1. Clone just the plugin (not the entire Moss repo)
git clone --filter=blob:none --sparse -b claude-code-plugin https://github.com/usemoss/moss.git claude-moss
cd claude-moss
git sparse-checkout set packages/claude-code-plugin
cd packages/claude-code-plugin

# 2. Install and build
npm install && npm run build

# 3. Add to Claude Code (run from packages/claude-code-plugin/)
PLUGIN_DIR=$(pwd)

claude mcp add \
  -e MOSS_PROJECT_ID=your-project-id \
  -e MOSS_PROJECT_KEY=your-project-key \
  -e MOSS_INDEX_NAME=your-index-name \
  -e NODE_PATH=$PLUGIN_DIR/node_modules \
  -s user \
  moss-search -- node $PLUGIN_DIR/plugin/scripts/mcp-launcher.cjs
```

This installs the MCP server (11 tools, index preload) permanently. For auto-search hooks and skills, also run:

```bash
claude --plugin-dir $PLUGIN_DIR/plugin
```

> **Note:** `--plugin-dir` is per-session. To make it permanent, add it as a shell alias:
> ```bash
> alias claude='claude --plugin-dir /path/to/packages/claude-code-plugin/plugin'
> ```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MOSS_PROJECT_ID` | Yes | From [moss.dev](https://moss.dev) dashboard |
| `MOSS_PROJECT_KEY` | Yes | From [moss.dev](https://moss.dev) dashboard |
| `MOSS_INDEX_NAME` | No | Default index for auto-search and preload |
| `MOSS_AUTO_SEARCH` | No | `true` (default) or `false` to disable |

## What It Does

### Auto-Context Injection

On every prompt, the plugin checks if it looks like a knowledge-seeking question. If so, it queries your Moss index and injects 1-3 relevant snippets as context before Claude responds. Pure edit commands ("rename this variable") are skipped.

### Conversation Capture

After Claude finishes responding, the plugin captures the conversation and stores it in your Moss index. Your knowledge base grows automatically over time.

### MCP Tools (11)

Claude can call these directly when needed:

| Tool | Description |
|------|-------------|
| `query` | Semantic search over an index |
| `load_index` | Load index into memory for ~5ms queries |
| `sync_project` | Hash-based incremental codebase indexing |
| `list_indexes` | List all project indexes |
| `create_index` | Create a new index |
| `add_docs` | Add documents to an index |
| `delete_docs` | Delete documents by ID |
| `get_index` | Get index metadata |
| `get_docs` | Retrieve documents |
| `delete_index` | Delete an index |
| `get_job_status` | Check async job status |

### Skills

| Command | Description |
|---------|-------------|
| `/moss-search <query>` | Search indexes with query-angle hints for debugging, architecture, review, refactoring |
| `/moss-index [name]` | Incrementally sync codebase files into a Moss index |

### Index Preload

If `MOSS_INDEX_NAME` is set, the MCP server preloads the index on startup. Queries start on cloud (~200ms) and become local (~5ms) after preload completes.

## Architecture

```
Claude Code
  ├── MCP server (moss-search)
  │     11 tools + index preload
  │
  ├── SessionStart hook
  │     prints status line
  │
  ├── UserPromptSubmit hook
  │     auto-search → inject context
  │
  └── Stop hook
        capture conversations → Moss
```

## Development

```bash
cd packages/claude-code-plugin
npm install
npm run build
npm run typecheck
```

## License

BSD-2-Clause

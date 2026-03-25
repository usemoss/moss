# claude-moss

Moss semantic search plugin for Claude Code. Auto-injects relevant context from your Moss indexes on every prompt, captures conversations as searchable memory, and provides tools for index management.

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- Node.js 18+
- A Moss account — sign up at [moss.dev](https://moss.dev)

## Installation

### 1. Get your Moss credentials

Go to [moss.dev](https://moss.dev), create a project, and grab your **Project ID** and **Project Key**. Create an index and add your documents.

### 2. Configure credentials

```bash
mkdir -p ~/.moss-claude
cat > ~/.moss-claude/settings.json << 'EOF'
{
  "projectId": "your-project-id",
  "projectKey": "your-project-key",
  "indexName": "your-index-name"
}
EOF
```

### 3. Install the plugin

```bash
git clone --filter=blob:none --sparse -b claude-code-plugin https://github.com/usemoss/moss.git claude-moss
cd claude-moss
git sparse-checkout set packages/claude-code-plugin
cd packages/claude-code-plugin
npm install && npm run build
claude plugin install ./plugin
```

### 4. Start Claude Code

```bash
claude
```

Everything loads automatically — MCP tools, auto-search hooks, skills. No flags needed.

### Verify

```
/moss-search test query
```

## Settings

All settings go in `~/.moss-claude/settings.json`:

```json
{
  "projectId": "your-project-id",
  "projectKey": "your-project-key",
  "indexName": "your-default-index",
  "autoSearch": true,
  "topK": 3,
  "scoreThreshold": 0.3
}
```

Environment variables (`MOSS_PROJECT_ID`, `MOSS_PROJECT_KEY`, `MOSS_INDEX_NAME`, `MOSS_AUTO_SEARCH`) override the settings file if set.

## What It Does

### Auto-Context Injection

On every prompt, the plugin queries your Moss index and injects 1-3 relevant snippets as context before Claude responds. Pure edit commands ("rename this variable") are skipped.

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
| `/moss-search <query>` | Search indexes — adapts queries for debugging, architecture, review, refactoring |
| `/moss-index [name]` | Incrementally sync codebase files into a Moss index |

### Index Preload

If `indexName` is set, the MCP server preloads the index on startup for fast local queries.

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

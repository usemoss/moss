# claude-moss

Moss semantic search plugin for Claude Code. Auto-injects relevant context from your Moss indexes on every prompt, captures conversations as searchable memory, and provides tools for index management.

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- Node.js 18+
- A Moss account — sign up at [moss.dev](https://moss.dev)

## Installation

### 1. Get your Moss credentials

Go to [moss.dev](https://moss.dev), create a project, and grab your **Project ID** and **Project Key**. Create an index and add your documents.

### 2. Configure settings

```bash
mkdir -p ~/.moss-claude
cat > ~/.moss-claude/settings.json << 'EOF'
{
  "projectId": "your-project-id",
  "projectKey": "your-project-key",
  "indexName": "your-index-name",
  "autoSearch": true,
  "localServer": true,
  "topK": 3,
  "scoreThreshold": 0.3
}
EOF
```

| Setting | Default | Description |
|---------|---------|-------------|
| `projectId` | — | Moss project ID (required) |
| `projectKey` | — | Moss project key (required) |
| `indexName` | — | Default index for auto-search and local server |
| `autoSearch` | `true` | Inject relevant context on every prompt |
| `localServer` | `true` | Start local query server on session start |
| `topK` | `3` | Number of results to return |
| `scoreThreshold` | `0.3` | Minimum similarity score (0-1) |

Environment variables (`MOSS_PROJECT_ID`, `MOSS_PROJECT_KEY`, `MOSS_INDEX_NAME`, `MOSS_AUTO_SEARCH`) override the settings file if set.

### 3. Install the plugin

In Claude Code, run:

```
/plugin marketplace add usemoss/moss
/plugin install claude-moss@moss
```

### 4. Install the local query server runtime

The plugin runs a local query server that loads your index into memory and serves queries over a Unix socket in <10ms. It requires `onnxruntime-node` (a native dependency that can't be bundled).

Install it in the plugin source directory:

```bash
cd ~/.claude/plugins/marketplaces/moss/packages/claude-code-plugin
npm install onnxruntime-node
```

Or install globally:

```bash
npm install -g onnxruntime-node
```

The local server starts automatically on session start when `indexName` is set. Without `onnxruntime-node`, the server won't start and auto-search will not work.

### 5. Restart Claude Code

Everything loads automatically — MCP tools, auto-search hooks, local query server, and skills.

### Verify

```
/claude-moss:moss-search test query
```

Check the local server:

```bash
ls -la /tmp/moss-claude/query.sock    # socket file exists
cat /tmp/moss-claude/query.pid        # server PID
```

## What It Does

### Auto-Context Injection

On every prompt, the plugin queries your Moss index and injects 1-3 relevant snippets as context before Claude responds. Pure edit commands ("rename this variable") are skipped.

Queries run locally over a Unix socket in <10ms.

### Local Query Server

A background Node.js process that:

1. Starts automatically on `SessionStart` as a detached child process
2. Loads the configured index into memory via the Moss SDK (`loadIndex`)
3. Listens on `/tmp/moss-claude/query.sock` for query requests
4. Serves queries in <10ms using local inference (onnxruntime-node)
5. Survives across hook invocations and is shared between concurrent sessions

The server requires `onnxruntime-node` installed separately. First run downloads the embedding model and index data (~15-30s), subsequent starts use the cached copy.

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

## Architecture

```
Claude Code
  ├── MCP server (moss-search)
  │     11 tools via stdio transport
  │
  ├── SessionStart hook
  │     prints status line
  │     spawns local query server (detached, background)
  │
  ├── UserPromptSubmit hook
  │     auto-search → local socket query → inject context
  │
  ├── Stop hook
  │     capture conversations → Moss
  │
  └── Local Query Server (background process)
        /tmp/moss-claude/query.sock
        loads index via SDK + onnxruntime-node
        serves queries <10ms
```

## Development

```bash
cd packages/claude-code-plugin
npm install
npm run build      # builds 5 bundles in plugin/scripts/
npm run typecheck
```

### Build output

| Bundle | Purpose |
|--------|---------|
| `mcp-launcher.cjs` | MCP stdio server (onnxruntime shimmed) |
| `session-init.cjs` | SessionStart hook (spawns local server) |
| `auto-search.cjs` | UserPromptSubmit hook (local socket query) |
| `capture.cjs` | Stop hook (conversation capture) |
| `local-server.cjs` | Background query server (onnxruntime external) |

### Installing to cache after changes

After building, copy the scripts to the plugin cache for Claude Code to pick up:

```bash
cp plugin/scripts/*.cjs ~/.claude/plugins/cache/moss/claude-moss/0.1.0/scripts/
```

Then restart Claude Code.

## License

BSD-2-Clause

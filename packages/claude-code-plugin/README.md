# claude-moss

Moss semantic search plugin for Claude Code. Turns your Moss indexes into persistent project memory — auto-injecting relevant context on every prompt, providing MCP tools for explicit retrieval, and surfacing workflow prompts as slash commands.

## What it does

- **Auto context injection** — On knowledge-seeking prompts ("how does X work?", "why is this broken?"), the plugin queries your Moss index and injects relevant chunks before Claude responds.
- **10 MCP tools** — Full Moss index and document management via `@moss-tools/mcp-server`.
- **4 workflow prompts** — `/mcp__moss__investigate_bug`, `/mcp__moss__understand_system`, `/mcp__moss__plan_refactor`, `/mcp__moss__review_with_context`.
- **Index preload** — If `MOSS_INDEX_NAME` is set, the default index is preloaded on startup for sub-10ms queries.

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- [Moss](https://moss.dev) project credentials (free tier available)
- Node.js 18+

## Installation

```bash
# Clone and build
git clone https://github.com/usemoss/moss.git
cd moss/packages/claude-code-plugin
npm install
npm run build

# Install in Claude Code
claude plugin add /absolute/path/to/packages/claude-code-plugin/plugin
```

## Configuration

### Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MOSS_PROJECT_ID` | Yes | Your Moss project ID (from [moss.dev](https://moss.dev)) |
| `MOSS_PROJECT_KEY` | Yes | Your Moss project key |
| `MOSS_INDEX_NAME` | No | Default index for auto-search and preload |
| `MOSS_AUTO_SEARCH` | No | `true` (default) or `false` to disable auto-context injection |

### Settings file (alternative)

Create `${CLAUDE_PLUGIN_DATA}/settings.json`:

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

Environment variables take precedence over the settings file.

## Use cases

### V1 — Built-in

- **Repo memory** — "How does authentication work here?" auto-retrieves relevant code and docs.
- **Debugging** — "Why does the payment endpoint return 500?" searches for related errors, fixes, runbooks.
- **Architecture** — "Explain the caching strategy" finds indexed design docs and ADRs.
- **Explicit search** — Claude uses MCP tools when deeper or targeted retrieval is needed.

### V2 — Enabled by the same mechanism

- **Refactor planning** — Search for similar patterns, prior migrations, blast radius.
- **PR/review prep** — Find invariants, similar codepaths, known caveats.
- **Onboarding** — Answer "how does billing work in this repo?" from indexed code + docs.
- **Cross-repo memory** — Index multiple repos for platform-wide questions.

## Auto-search behavior

The UserPromptSubmit hook is **selective, not always-on**. It triggers on:

- Knowledge-seeking: "how does", "where is", "why does", "explain"
- Search intent: "find", "search", "look up"
- Debugging: "broken", "failing", "error", "bug", "crash"
- Architecture: "architecture", "design", "implementation"
- Questions (prompts containing `?`)

It skips:

- Pure editing: "rename this variable", "change X to Y"
- Generic coding: "write a function that", "create a class"
- Obvious local tasks: "fix the typo on line 42"
- Very short (<10 chars) or very long (>500 chars) prompts

## MCP tools

Provided by `@moss-tools/mcp-server`:

| Tool | Description |
|------|-------------|
| `query` | Semantic search over an index |
| `load_index` | Download index into memory for ~5ms local queries |
| `list_indexes` | List all project indexes |
| `create_index` | Create a new index with documents |
| `add_docs` | Add documents to an index |
| `delete_docs` | Delete documents by ID |
| `get_index` | Get index metadata |
| `get_docs` | Retrieve documents |
| `delete_index` | Delete an index |
| `get_job_status` | Check async job status |

## MCP prompts (slash commands)

| Command | Description |
|---------|-------------|
| `/mcp__moss__investigate_bug` | Debug errors by searching for related runbooks, fixes, docs |
| `/mcp__moss__understand_system` | Map architecture: modules, docs, entrypoints |
| `/mcp__moss__plan_refactor` | Find patterns, migrations, blast radius |
| `/mcp__moss__review_with_context` | Retrieve invariants, caveats for code review |

## Indexing strategy

### What to index

- **Code chunks** — with file path + line range metadata
- **Docs / ADRs / runbooks** — with title + section metadata
- **API docs** — generated reference documentation
- **Optionally** — issue templates, postmortems, migration notes

### Recommended layout

| Index | Contents |
|-------|----------|
| `codebase` | Local repo code chunks |
| `docs` | Markdown docs, ADRs, runbooks |
| `platform` | Cross-repo knowledge, internal docs |

Set `MOSS_INDEX_NAME` to the most commonly useful one. Use MCP tools to search others explicitly.

### Creating an index

Use the MCP tools or the Moss SDK directly:

```bash
# Via MCP (in Claude Code)
# Ask Claude: "Create a Moss index called 'docs' with these documents..."

# Via SDK
npx tsx -e "
import { MossClient } from '@inferedge/moss';
const client = new MossClient('your-id', 'your-key');
await client.createIndex('docs', [
  { id: 'readme', text: '...' },
  { id: 'architecture', text: '...' },
]);
"
```

## Architecture

```
Claude Code
  |-- MCP (stdio) --> mcp-launcher.cjs
  |                     imports @moss-tools/mcp-server (10 tools)
  |                     registers 4 MCP prompts
  |                     preloads MOSS_INDEX_NAME on startup
  |
  |-- SessionStart --> session-init.cjs
  |                     prints status line, exits 0
  |
  +-- UserPromptSubmit --> auto-search.cjs
                            selective trigger heuristic
                            direct cloud fetch to Moss /query
                            bounded dedup (last 50 doc IDs)
                            injects additionalContext
```

## Development

```bash
cd packages/claude-code-plugin
npm install
npm run build      # esbuild: src/ -> plugin/scripts/*.cjs
npm run typecheck   # tsc --noEmit
```

## License

BSD-2-Clause

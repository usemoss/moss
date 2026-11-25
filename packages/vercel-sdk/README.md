# @moss-tools/vercel-sdk

Vercel AI SDK 6 tool wrappers for [MOSS](https://moss.dev) semantic search.

Gives AI agents the ability to search, create indexes, and manage documents through MOSS — all via standard AI SDK `tool()` definitions.

## Install

```bash
npm install @moss-tools/vercel-sdk @moss-js/moss ai zod
```

## Usage

```typescript
import { MossClient } from '@moss-js/moss';
import { mossSearchTool, mossCreateIndexTool } from '@moss-tools/vercel-sdk';
import { generateText } from 'ai';
import { openai } from '@ai-sdk/openai';

const client = new MossClient('your-project-id', 'your-project-key');

const result = await generateText({
  model: openai('gpt-4o'),
  tools: {
    search: mossSearchTool({ client, indexName: 'docs' }),
    createIndex: mossCreateIndexTool({ client }),
  },
  maxSteps: 5,
  prompt: 'Find docs about neural networks and summarize them.',
});
```

## Available tools

| Factory | Description | Mutating |
| --- | --- | --- |
| `mossSearchTool` | Semantic search | No |
| `mossAddDocsTool` | Add documents to an index | Yes |
| `mossDeleteDocsTool` | Delete documents by ID | Yes |
| `mossCreateIndexTool` | Create a new index with documents | Yes |
| `mossLoadIndexTool` | Load an index into memory for fast local queries | No |
| `mossListIndexesTool` | List all indexes | No |

Mutating tools set `needsApproval: true` so the AI SDK can prompt for user confirmation.

## Tool options

All tool factories accept:

- `client` — a `MossClient` instance (required)
- `description` — override the default tool description

Search, loadIndex, addDocs, and deleteDocs also accept:

- `indexName` — prebind to a specific index. When omitted, the LLM must specify the index name as part of the tool input.

## Loading indexes

`@moss-js/moss` queries indexes loaded on the device. The search tool loads an index the first time it searches it, so that first call also downloads the index and warms its model. To avoid that delay, load the index before the agent runs, with `await client.loadIndex('docs')`.

After `mossAddDocsTool` or `mossDeleteDocsTool` changes an index that the search tool or `mossLoadIndexTool` loaded, they reload it so search sees the change. The reload is best effort: if it fails, the tool still reports the change, and the next search tries the reload again before it queries, falling back to the copy it has if that fails too, so it can return results from before the change. They don't reload an index you loaded with `client.loadIndex`, so if the agent can also add or delete documents, either let the search tool load the index or pass `{ autoRefresh: true }` to `client.loadIndex` so it picks up changes on its own.

## Upgrading from 0.1

0.1 took a `MossClient` from `@moss-dev/moss`, which reaches end of support on 2026-12-17. 0.2 takes a `MossClient` from `@moss-js/moss` 1.16 or later:

```bash
npm uninstall @moss-dev/moss
npm install @moss-tools/vercel-sdk@^0.2.0 @moss-js/moss
```

Then import `MossClient` from `@moss-js/moss`. The tools and their options are unchanged.

## Examples

### Prebound index (simpler schema for the LLM)

```typescript
const search = mossSearchTool({ client, indexName: 'docs' });
// LLM only needs to provide: { query, topK? }
```

### Dynamic index (LLM chooses the index)

```typescript
const search = mossSearchTool({ client });
// LLM must provide: { indexName, query, topK? }
```

### All tools

```typescript
import {
  mossSearchTool,
  mossLoadIndexTool,
  mossAddDocsTool,
  mossDeleteDocsTool,
  mossCreateIndexTool,
  mossListIndexesTool,
} from '@moss-tools/vercel-sdk';

const tools = {
  search: mossSearchTool({ client, indexName: 'docs' }),
  loadIndex: mossLoadIndexTool({ client, indexName: 'docs' }),
  addDocs: mossAddDocsTool({ client, indexName: 'docs' }),
  deleteDocs: mossDeleteDocsTool({ client, indexName: 'docs' }),
  createIndex: mossCreateIndexTool({ client }),
  listIndexes: mossListIndexesTool({ client }),
};
```

## License

See [LICENSE](./LICENSE).

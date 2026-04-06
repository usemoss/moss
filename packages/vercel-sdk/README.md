# @moss-tools/vercel-sdk

Vercel AI SDK 6 tool wrappers for [MOSS](https://moss.dev) semantic search.

Gives AI agents the ability to search, create indexes, and manage documents through MOSS — all via standard AI SDK `tool()` definitions.

## Install

```bash
npm install @moss-tools/vercel-sdk @moss-dev/moss ai zod
```

## Usage

```typescript
import { MossClient } from '@moss-dev/moss';
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
| `mossListIndexesTool` | List all indexes | No |

Mutating tools set `needsApproval: true` so the AI SDK can prompt for user confirmation.

## Tool options

All tool factories accept:

- `client` — a `MossClient` instance (required)
- `description` — override the default tool description

Search, addDocs, and deleteDocs also accept:

- `indexName` — prebind to a specific index. When omitted, the LLM must specify the index name as part of the tool input.

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
  mossAddDocsTool,
  mossDeleteDocsTool,
  mossCreateIndexTool,
  mossListIndexesTool,
} from '@moss-tools/vercel-sdk';

const tools = {
  search: mossSearchTool({ client, indexName: 'docs' }),
  addDocs: mossAddDocsTool({ client, indexName: 'docs' }),
  deleteDocs: mossDeleteDocsTool({ client, indexName: 'docs' }),
  createIndex: mossCreateIndexTool({ client }),
  listIndexes: mossListIndexesTool({ client }),
};
```

## License

See [LICENSE](./LICENSE).

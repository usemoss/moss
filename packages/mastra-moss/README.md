# @moss-tools/mastra

Moss semantic search tools for [Mastra](https://mastra.ai) agents.

Wraps Moss into `createTool()` primitives that drop straight into any Mastra agent. Sub-10ms lookups, no external embedder, no vector database to run.

## Installation

```bash
npm install @moss-tools/mastra @moss-dev/moss @mastra/core zod
```

## Prerequisites

- Moss project ID and project key — get them from the [Moss Portal](https://portal.usemoss.dev)
- Node.js 18+

## Quickstart

```typescript
import { Agent } from '@mastra/core/agent';
import { MossClient } from '@moss-dev/moss';
import { mossSearchTool } from '@moss-tools/mastra';

const client = new MossClient(
  process.env.MOSS_PROJECT_ID!,
  process.env.MOSS_PROJECT_KEY!
);

// Load the index once at startup for sub-10ms queries
await client.loadIndex('my-index');

const agent = new Agent({
  id: 'support-agent',
  name: 'Knowledge Support Copilot',
  instructions: 'Use moss_search to find relevant information before answering.',
  model: 'openai/gpt-4.1-mini',
  tools: {
    search: mossSearchTool({ client, indexName: 'my-index' }),
  },
});

const response = await agent.generate('What is your refund policy?');
console.log(response.text);
```

## Available tools

### `mossSearchTool`

Searches a Moss index and returns ranked documents.

```typescript
import { mossSearchTool } from '@moss-tools/mastra';

// Pre-bound to an index — LLM only needs to supply { query }
const search = mossSearchTool({ client, indexName: 'my-index' });

// Dynamic — LLM supplies { indexName, query }
const search = mossSearchTool({ client });
```

**Options:**

| Option | Default | Description |
|---|---|---|
| `client` | (required) | `MossClient` instance |
| `indexName` | — | Pre-bind to an index; when omitted the LLM must provide it |
| `topK` | `5` | Number of results to return |
| `alpha` | `0.8` | Search blend: 1.0 = semantic only, 0.0 = keyword only |
| `id` | `"moss_search"` | Mastra tool ID |
| `description` | *(auto)* | Tool description shown to the LLM |

### `mossAddDocsTool`

Adds or upserts documents into a Moss index. Useful for agents that learn and store information during a conversation.

```typescript
import { mossAddDocsTool } from '@moss-tools/mastra';

const addDocs = mossAddDocsTool({ client, indexName: 'my-index' });
```

**Options:**

| Option | Default | Description |
|---|---|---|
| `client` | (required) | `MossClient` instance |
| `indexName` | — | Pre-bind to an index |
| `id` | `"moss_add_docs"` | Mastra tool ID |
| `description` | *(auto)* | Tool description shown to the LLM |

## Agent with both tools

```typescript
const agent = new Agent({
  id: 'learning-agent',
  instructions:
    'You are a support assistant. Search the knowledge base with moss_search. ' +
    'If you learn something new that should be remembered, store it with moss_add_docs.',
  model: 'openai/gpt-4.1-mini',
  tools: {
    search: mossSearchTool({ client, indexName: 'support-kb' }),
    addDocs: mossAddDocsTool({ client, indexName: 'support-kb' }),
  },
});
```

## License

BSD 2-Clause — see [LICENSE](LICENSE).

## Support

- [Moss Docs](https://docs.moss.dev)
- [Moss Discord](https://discord.gg/eMXExuafBR)
- [Mastra Docs](https://mastra.ai/docs)

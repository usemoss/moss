import { createTool } from '@mastra/core/tools';
import { z } from 'zod';
import type { MossClient } from '@moss-dev/moss';

export interface MossSearchToolOptions {
  /** Moss client instance. */
  client: MossClient;
  /** Pre-bind to a specific index. When omitted the LLM must supply `indexName`. */
  indexName?: string;
  /** Number of results to return (default: 5). */
  topK?: number;
  /** Hybrid search blend — 1.0 = semantic only, 0.0 = keyword only (default: 0.8). */
  alpha?: number;
  /** Override the Mastra tool `id`. */
  id?: string;
  /** Override the tool description shown to the LLM. */
  description?: string;
}

export interface MossAddDocsToolOptions {
  /** Moss client instance. */
  client: MossClient;
  /** Pre-bind to a specific index. When omitted the LLM must supply `indexName`. */
  indexName?: string;
  /** Override the Mastra tool `id`. */
  id?: string;
  /** Override the tool description shown to the LLM. */
  description?: string;
}

const docSchema = z.object({
  id: z.string().describe('Unique document identifier.'),
  text: z.string().describe('Text content to embed and store.'),
  metadata: z.record(z.string()).optional().describe('Optional key-value metadata.'),
});

/**
 * Creates a Mastra tool that searches a Moss index.
 *
 * @example
 * ```ts
 * import { Agent } from '@mastra/core/agent';
 * import { MossClient } from '@moss-dev/moss';
 * import { mossSearchTool } from '@moss-tools/mastra';
 *
 * const client = new MossClient(process.env.MOSS_PROJECT_ID!, process.env.MOSS_PROJECT_KEY!);
 * await client.loadIndex('my-index');
 *
 * const agent = new Agent({
 *   id: 'support-agent',
 *   instructions: 'Use moss_search to answer questions from the knowledge base.',
 *   model: 'openai/gpt-4.1-mini',
 *   tools: { search: mossSearchTool({ client, indexName: 'my-index' }) },
 * });
 * ```
 */
export function mossSearchTool(options: MossSearchToolOptions) {
  const {
    client,
    indexName: boundIndex,
    topK = 5,
    alpha = 0.8,
    id = 'moss_search',
    description,
  } = options;

  const baseFields = {
    query: z.string().describe('The semantic search query.'),
  };

  const inputSchema =
    boundIndex != null
      ? z.object(baseFields)
      : z.object({
          indexName: z.string().describe('Name of the Moss index to search.'),
          ...baseFields,
        });

  return createTool({
    id,
    description:
      description ??
      'Search the knowledge base using Moss semantic search. Returns the most relevant documents for a given query.',
    inputSchema,
    execute: async (input) => {
      const index = boundIndex ?? (input as { indexName: string }).indexName;
      const result = await client.query(index, input.query, { topK, alpha });
      return result.docs.map((doc) => ({
        text: doc.text,
        score: doc.score,
        ...(doc.metadata ? { metadata: doc.metadata } : {}),
      }));
    },
  });
}

/**
 * Creates a Mastra tool that adds or upserts documents into a Moss index.
 * Useful for agents that learn and store new information during a conversation.
 */
export function mossAddDocsTool(options: MossAddDocsToolOptions) {
  const { client, indexName: boundIndex, id = 'moss_add_docs', description } = options;

  const baseFields = {
    docs: z
      .array(docSchema)
      .min(1)
      .max(50)
      .describe('Documents to add or update in the index (1-50).'),
  };

  const inputSchema =
    boundIndex != null
      ? z.object(baseFields)
      : z.object({
          indexName: z.string().describe('Name of the Moss index to add documents to.'),
          ...baseFields,
        });

  return createTool({
    id,
    description:
      description ??
      'Add or update documents in a Moss knowledge base index. Use this to store new information for future retrieval.',
    inputSchema,
    execute: async (input) => {
      const index = boundIndex ?? (input as { indexName: string }).indexName;
      const result = await client.addDocs(index, input.docs, { upsert: true });
      return { jobId: result.jobId, docCount: result.docCount };
    },
  });
}

import { tool } from 'ai';
import { z } from 'zod';
import type { MossClient } from '@moss-dev/moss';

export interface MossCreateIndexToolOptions {
  client: MossClient;
  description?: string;
}

export interface MossListIndexesToolOptions {
  client: MossClient;
  description?: string;
}

export interface MossLoadIndexToolOptions {
  client: MossClient;
  indexName?: string;
  description?: string;
}

const docSchema = z.object({
  id: z.string().describe('Unique identifier for the document.'),
  text: z.string().describe('Text content to embed and index.'),
  metadata: z
    .record(z.string())
    .optional()
    .describe('Optional key-value metadata.'),
});

export function mossCreateIndexTool(options: MossCreateIndexToolOptions) {
  const { client, description } = options;

  return tool({
    description:
      description ??
      'Create a new MOSS semantic search index with initial documents.',
    inputSchema: z.object({
      indexName: z
        .string()
        .describe('Name for the new index.'),
      docs: z
        .array(docSchema)
        .min(1)
        .max(100)
        .describe('Initial documents (1-100).'),
      modelId: z
        .enum(['moss-minilm', 'moss-mediumlm'])
        .default('moss-minilm')
        .describe('Embedding model to use.'),
    }),
    needsApproval: true,
    execute: async (input) => {
      return client.createIndex(input.indexName, input.docs, {
        modelId: input.modelId,
      });
    },
  });
}

export function mossLoadIndexTool(options: MossLoadIndexToolOptions) {
  const { client, indexName: boundIndexName, description } = options;

  const baseFields = {
    autoRefresh: z
      .boolean()
      .default(false)
      .describe('Enable auto-refresh polling to keep the index up-to-date.'),
    pollingIntervalInSeconds: z
      .number()
      .int()
      .min(60)
      .optional()
      .describe('Polling interval in seconds when autoRefresh is enabled (min 60).'),
  };

  const inputSchema = boundIndexName != null
    ? z.object(baseFields)
    : z.object({
        indexName: z
          .string()
          .describe('Name of the index to load into memory.'),
        ...baseFields,
      });

  return tool({
    description:
      description ??
      'Load a MOSS index into memory for fast local querying. Without loading, queries go to the cloud API. After loading, queries run in-memory.',
    inputSchema,
    execute: async (input) => {
      const resolvedIndexName =
        boundIndexName ?? (input as unknown as { indexName: string }).indexName;
      const opts: Record<string, unknown> = {};
      if (input.autoRefresh) {
        opts.autoRefresh = true;
        if (input.pollingIntervalInSeconds != null) {
          opts.pollingIntervalInSeconds = input.pollingIntervalInSeconds;
        }
      }
      const loaded = await client.loadIndex(resolvedIndexName, opts);
      return { indexName: loaded, status: 'loaded' };
    },
  });
}

export function mossListIndexesTool(options: MossListIndexesToolOptions) {
  const { client, description } = options;

  return tool({
    description:
      description ?? 'List all available MOSS semantic search indexes.',
    inputSchema: z.object({}),
    execute: async () => {
      return client.listIndexes();
    },
  });
}

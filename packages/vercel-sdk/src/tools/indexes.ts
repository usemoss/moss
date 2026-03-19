import { tool } from 'ai';
import { z } from 'zod';
import type { MossClient } from '@inferedge/moss';

export interface MossCreateIndexToolOptions {
  client: MossClient;
  description?: string;
}

export interface MossListIndexesToolOptions {
  client: MossClient;
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

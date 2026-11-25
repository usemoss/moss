import { tool } from 'ai';
import { z } from 'zod';
import type { MossClient } from '@moss-js/moss';
import { ensureLoaded } from './loaded.js';

export interface MossSearchToolOptions {
  client: MossClient;
  indexName?: string;
  description?: string;
}

export function mossSearchTool(options: MossSearchToolOptions) {
  const { client, indexName: boundIndexName, description } = options;

  const baseFields = {
    query: z.string().describe('The search query text.'),
    topK: z
      .number()
      .int()
      .min(1)
      .max(100)
      .default(5)
      .describe('Number of results to return (1-100, default 5).'),
  };

  const inputSchema = boundIndexName != null
    ? z.object(baseFields)
    : z.object({
        indexName: z
          .string()
          .describe('Name of the index to search.'),
        ...baseFields,
      });

  return tool({
    description:
      description ??
      'Search a MOSS semantic search index for documents matching a query.',
    inputSchema,
    execute: async (input) => {
      const resolvedIndexName =
        boundIndexName ?? (input as unknown as { indexName: string }).indexName;
      const query = () =>
        client.query(resolvedIndexName, input.query, { topK: input.topK });
      try {
        return await query();
      } catch (err) {
        if ((err as { code?: string } | null)?.code !== 'NOT_FOUND') throw err;
        await ensureLoaded(client, resolvedIndexName);
        return query();
      }
    },
  });
}

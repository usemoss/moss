import { tool } from 'ai';
import { z } from 'zod';
import type { MossClient } from '@inferedge/moss';

export interface MossAddDocsToolOptions {
  client: MossClient;
  indexName?: string;
  description?: string;
}

export interface MossDeleteDocsToolOptions {
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

export function mossAddDocsTool(options: MossAddDocsToolOptions) {
  const { client, indexName: boundIndexName, description } = options;

  const baseFields = {
    docs: z
      .array(docSchema)
      .min(1)
      .max(100)
      .describe('Documents to add (1-100).'),
  };

  const inputSchema = boundIndexName != null
    ? z.object(baseFields)
    : z.object({
        indexName: z
          .string()
          .describe('Name of the index to add documents to.'),
        ...baseFields,
      });

  return tool({
    description:
      description ??
      'Add documents to a MOSS semantic search index.',
    inputSchema,
    needsApproval: true,
    execute: async (input) => {
      const resolvedIndexName =
        boundIndexName ?? (input as unknown as { indexName: string }).indexName;
      return client.addDocs(resolvedIndexName, input.docs);
    },
  });
}

export function mossDeleteDocsTool(options: MossDeleteDocsToolOptions) {
  const { client, indexName: boundIndexName, description } = options;

  const baseFields = {
    docIds: z
      .array(z.string())
      .min(1)
      .max(100)
      .describe('IDs of documents to delete (1-100).'),
  };

  const inputSchema = boundIndexName != null
    ? z.object(baseFields)
    : z.object({
        indexName: z
          .string()
          .describe('Name of the index to delete documents from.'),
        ...baseFields,
      });

  return tool({
    description:
      description ??
      'Delete documents from a MOSS semantic search index by their IDs.',
    inputSchema,
    needsApproval: true,
    execute: async (input) => {
      const resolvedIndexName =
        boundIndexName ?? (input as unknown as { indexName: string }).indexName;
      return client.deleteDocs(resolvedIndexName, input.docIds);
    },
  });
}

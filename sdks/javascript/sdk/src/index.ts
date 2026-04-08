/**
 * Moss Semantic Search SDK
 *
 * Powerful TypeScript SDK for local semantic search using state-of-the-art embedding models.
 *
 * @example
 * ```typescript
 * import { MossClient } from '@moss-dev/moss';
 *
 * const client = new MossClient('your-project-id', 'your-project-key');
 *
 * // Create an index with documents
 * await client.createIndex('knowledge-base', [
 *   { id: '1', text: 'Machine learning algorithms for data analysis' },
 *   { id: '2', text: 'Natural language processing techniques' }
 * ]);
 *
 * // Query the index
 * await client.loadIndex('knowledge-base');
 * const results = await client.query('knowledge-base', 'AI and data science');
 * ```
 */

export { MossClient } from "./client/mossClient";

// SDK-specific types
export type { ISODate, MossModel, CreateIndexOptions } from "./models";

// Re-export moss-core types directly
export type {
  DocumentInfo,
  QueryResultDocumentInfo,
  SearchResult,
  QueryOptions,
  GetDocumentsOptions,
  MutationResult,
  RefreshResult,
  JobStatusResponse,
  JobStatus,
  JobPhase,
} from "@moss-dev/moss-core";

// SDK-specific types (extended or unique to SDK)
export type {
  LoadIndexOptions,
  MutationOptions,
  JobProgress,
} from "./models";

/**
 * Shared types for the Moss React Native / Expo module.
 * Mirrors the public surface of `@moss-dev/moss` closely enough that
 * examples transfer across runtimes.
 */

export type MossModel = 'moss-minilm' | 'moss-mediumlm' | 'moss-litelm' | 'custom' | (string & {});

export interface DocumentInfo {
  id: string;
  text: string;
  metadata?: Record<string, string>;
  embedding?: number[];
  /** Opaque structured payload (e.g. JSON string). Not embedded or searched. */
  payload?: string;
}

export interface QueryResultDocumentInfo {
  id: string;
  text: string;
  score: number;
  metadata?: Record<string, string>;
  payload?: string;
}

export interface SearchResult {
  docs: QueryResultDocumentInfo[];
  query: string;
  /** Wall-clock query time in milliseconds. */
  timeMs: number;
}

export interface QueryOptions {
  topK?: number;
  /** Hybrid weight: 1.0 = dense only, 0.0 = sparse only. Default 0.8. */
  alpha?: number;
  /** Metadata filter as a JSON string (engine filter format). */
  filterJson?: string;
}

export interface ModelRef {
  id: string;
  version?: string | null;
}

export interface IndexInfo {
  id: string;
  name: string;
  status: string;
  docCount: number;
  model: ModelRef;
  version?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface MutationResult {
  jobId: string;
  indexName: string;
  docCount: number;
}

export interface CreateIndexOptions {
  modelId?: MossModel;
}

export interface LoadIndexOptions {
  autoRefresh?: boolean;
  /** Poll interval in seconds when `autoRefresh` is true. Default 600. */
  pollingIntervalSeconds?: number;
  /** Sandbox path used to cache the index on disk across launches. */
  cachePath?: string;
}

export interface MutationOptions {
  upsert?: boolean;
}

export class MossError extends Error {
  readonly code: number;

  constructor(code: number, message: string) {
    super(message);
    this.name = 'MossError';
    this.code = code;
  }
}

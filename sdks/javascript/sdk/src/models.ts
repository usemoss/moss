
/**
 * ISO 8601 date string format.
 * @example "2025-09-26T15:04:05Z"
 */
export type ISODate = string;

/**
 * Available embedding models for text-to-vector conversion.
 *
 * Each model offers different trade-offs between speed, accuracy, and resource usage:
 *
 * - **`"moss-minilm"`**: Lightweight model optimized for speed and efficiency.
 *   Best for applications requiring fast response times with moderate accuracy requirements.
 *
 * - **`"moss-mediumlm"`**: Balanced model offering higher accuracy with reasonable performance.
 *   Best for applications where search quality is important and moderate latency is acceptable.
 *
 * - **`"custom"`**: Use this when providing pre-computed embeddings from external sources.
 *   No embedding model is loaded. All documents must include embeddings, and all queries
 *   must provide embeddings via QueryOptions.embedding.
 */
export type MossModel = "moss-minilm" | "moss-mediumlm" | "custom";

/**
 * Reference to a model with version information.
 */
export interface ModelRef {
  /**
   * Model identifier.
   */
  id: string | null;

  /**
   * Model version (semver/commit).
   */
  version: string | null;
}

/**
 * Information about an index including metadata and status.
 */
export interface IndexInfo {
  /**
   * Unique identifier of the index.
   */
  id: string;

  /**
   * Human-readable name of the index.
   */
  name: string;

  /**
   * Index build/format version (semver).
   */
  version: string | null;

  /**
   * Current status of the index.
   */
  status: "NotStarted" | "Building" | "Ready" | "Failed";

  /**
   * Number of documents in the index.
   */
  docCount: number;

  /**
   * When the index was created.
   */
  createdAt: ISODate;

  /**
   * When the index was last updated.
   */
  updatedAt: ISODate;

  /**
   * Model used for embeddings.
   */
  model: ModelRef;
}


/**
 * Document that can be indexed and retrieved.
 */
export interface DocumentInfo {
  /**
   * Unique identifier within an index.
   */
  id: string;

  /**
   * REQUIRED canonical text to embed/search.
   */
  text: string;

  /**
   * Optional metadata associated with the document.
   */
  metadata?: Record<string, string>;

  /**
   * Optional caller-provided embedding vector.
   */
  embedding?: number[];
}


/**
 * Document result from a query with similarity score.
 */
export interface QueryResultDocumentInfo extends DocumentInfo {
  /**
   * Similarity score (0-1, higher = more similar).
   */
  score: number;
}

/**
 * Search operation result.
 */
export interface SearchResult {
  /**
   * Matching documents ordered by similarity score.
   */
  docs: QueryResultDocumentInfo[];

  /**
   * The original search query.
   */
  query: string;

  /**
   * Name of the index that was searched.
   */
  indexName?: string;

  /**
   * Time taken to execute the search in milliseconds.
   */
  timeTakenInMs?: number;
}

/**
 * Optional parameters for semantic queries.
 */
export interface QueryOptions {
  /**
   * Caller-provided embedding vector. When supplied, the service/client skips embedding generation.
   */
  embedding?: number[];

  /**
   * Number of top results to return. Overrides method-level defaults.
   */
  topK?: number;

  /**
   * Weight for hybrid search fusion (0.0 to 1.0).
   * @default 0.8
   */
  alpha?: number;

  /**
   * Optional metadata filter to narrow query results.
   *
   * Supports field conditions and logical operators:
   * - Field: `{ field: "city", condition: { $eq: "NYC" } }`
   * - And: `{ $and: [filter, filter, ...] }`
   * - Or: `{ $or: [filter, filter, ...] }`
   *
   * Condition operators: `$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`, `$in`, `$nin`, `$near`
   */
  filter?: Record<string, unknown>;
}


/**
 * Options for retrieving documents from an index.
 */
export interface GetDocumentsOptions {
  /**
   * Optional array of document IDs to retrieve.
   * If omitted, returns all documents.
   */
  docIds?: string[];
}

/**
 * Options for adding documents to a local in-memory index.
 */
export interface AddDocumentsOptions {
  /**
   * Whether to update existing documents with the same ID.
   * @default true
   */
  upsert?: boolean;
}


/**
 * Complete serialized representation of an index for local .moss file storage.
 *
 * Contains all data necessary to recreate an index, including configuration,
 * documents, and pre-computed embeddings.
 */
export interface SerializedIndex {
  /**
   * Name of the index.
   */
  name: string;

  /**
   * Index build/format version (semver).
   */
  version: string;

  /**
   * Model bound to this index.
   */
  model: ModelRef;

  /**
   * Embedding dimensionality.
   */
  dimension: number;

  /**
   * Embedding vectors (rows = embedding vectors).
   */
  embeddings: number[][];

  /**
   * Document IDs parallel to embeddings.
   */
  docIds: string[];
}

/**
 * Progress update passed to the `onProgress` callback during async operations.
 */
export interface JobProgress {
  jobId: string;
  status: "pending_upload" | "uploading" | "building" | "completed" | "failed";
  progress: number;
  currentPhase: "downloading" | "deserializing" | "generating_embeddings" | "building_index" | "uploading" | "cleanup" | null;
}


/**
 * Options for creating an index.
 */
export interface CreateIndexOptions {
  /**
   * Embedding model to use. Defaults to "moss-minilm", or "custom" if
   * documents have pre-computed embeddings.
   */
  modelId?: string;

  /**
   * Callback invoked with progress updates (~every 2s) while the server is processing.
   */
  onProgress?: (progress: JobProgress) => void;
}

/**
 * Options for async mutation operations (addDocs, deleteDocs).
 * Extends moss-core MutationOptions with SDK-specific onProgress callback.
 */
export interface MutationOptions {
  /**
   * Whether to update existing documents with the same ID.
   * Only applies to addDocs.
   * @default true
   */
  upsert?: boolean;

  /**
   * Callback invoked with progress updates (~every 2s) while the server is processing.
   */
  onProgress?: (progress: JobProgress) => void;
}

// MutationResult is exported directly from index.ts

/**
 * Raw server response from async mutation operations (internal).
 */
export interface MutationResponse {
  jobId: string;
  status: "pending_upload" | "uploading" | "building" | "completed" | "failed";
}

// JobStatusResponse is exported directly from index.ts

// Cloud API request types (internal)

export interface RequestBody {
  action: string;
  projectId: string;
  indexName?: string;
}

export type HandleGetIndexOptions = RequestBody;

export type HandleListIndexesOptions = RequestBody;

export interface HandleDeleteIndexOptions extends RequestBody {
  indexName: string;
}

export interface HandleAddDocsOptions extends RequestBody {
  indexName: string;
  docs: DocumentInfo[];
  options?: { upsert?: boolean };
}

export interface HandleDeleteDocsOptions extends RequestBody {
  indexName: string;
  docIds: string[];
}

export interface HandleGetDocsOptions extends RequestBody {
  options?: GetDocumentsOptions;
}

export interface IndexAssetsUrls {
  indexUrl: string;
  jsonUrl: string;
}

// Init upload internal request/response types

export interface HandleInitUploadOptions extends RequestBody {
  indexName: string;
  docCount: number;
  dimension: number;
  modelId?: string;
}

export interface InitUploadResponse {
  jobId: string;
  uploadUrl: string;
  expiresIn: number;
}

export interface HandleStartBuildOptions extends RequestBody {
  jobId: string;
}

export interface StartBuildResponse {
  jobId: string;
  status: "pending_upload" | "uploading" | "building" | "completed" | "failed";
}

export interface HandleGetJobStatusOptions extends RequestBody {
  jobId: string;
}

export interface GetJobStatusResponse {
  jobId: string;
  status: "pending_upload" | "uploading" | "building" | "completed" | "failed";
  progress: number;
  currentPhase: "downloading" | "deserializing" | "generating_embeddings" | "building_index" | "uploading" | "cleanup" | null;
  error?: string | null;
  createdAt: string;
  updatedAt: string;
  completedAt: string | null;
}

/**
 * Options for loading an index with auto-refresh configuration.
 * Note: SDK makes fields optional with defaults, moss-core requires them.
 */
export interface LoadIndexOptions {
  /**
   * Whether to enable auto-refresh polling for this index.
   * When enabled, the index will periodically check for updates from the cloud.
   * @default false
   */
  autoRefresh?: boolean;

  /**
   * Polling interval in seconds. Only used when autoRefresh is true.
   * @default 600 (10 minutes)
   */
  pollingIntervalInSeconds?: number;

  /**
   * Filesystem path for caching index data to disk.
   * When set, downloaded indexes are persisted and reused on subsequent loads
   * if the cloud data hasn't changed. Auto-refresh also persists to cache.
   */
  cachePath?: string;
}

// RefreshResult is exported directly from index.ts

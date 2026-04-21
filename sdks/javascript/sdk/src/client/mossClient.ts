import { InternalMossClient } from "./internalMossClient";
import type {
  SearchResult,
  IndexInfo,
  DocumentInfo,
  GetDocumentsOptions,
  QueryOptions,
  MutationResult,
  JobStatusResponse,
} from "@moss-dev/moss-core";
import {
  LoadIndexOptions,
  CreateIndexOptions,
  MutationOptions,
  MossModel,
} from "../models";

const DEFAULT_MODEL_ID: MossModel = "moss-minilm";

/**
 * MossClient - Async-first semantic search client for vector similarity operations.
 *
 * All mutations (createIndex, addDocs, deleteDocs) are async operations
 * that run server-side and poll until complete.
 *
 * @example
 * ```typescript
 * import { MossClient } from '@moss-dev/moss';
 *
 * const client = new MossClient('your-project-id', 'your-project-key');
 *
 * // Create an index with documents (polls until complete)
 * const result = await client.createIndex('docs', [
 *   { id: '1', text: 'Machine learning fundamentals' },
 *   { id: '2', text: 'Deep learning neural networks' }
 * ]);
 *
 * // Add docs (polls until complete)
 * await client.addDocs('docs', [
 *   { id: '3', text: 'Natural language processing' }
 * ]);
 *
 * // Query the index
 * await client.loadIndex('docs');
 * const results = await client.query('docs', 'AI and neural networks');
 * ```
 */
export class MossClient {
  #internal: InternalMossClient;

  /**
   * Creates a new MossClient instance.
   * @param projectId - Your project identifier.
   * @param projectKey - Your project authentication key.
   */
  constructor(projectId: string, projectKey: string) {
    this.#internal = new InternalMossClient(projectId, projectKey);
  }


  /**
   * Creates a new index with the provided documents via async upload.
   *
   * Handles the full flow: init → upload → build → poll until complete.
   * Returns when the index is ready.
   *
   * When all documents have pre-computed embeddings, they are serialized as raw
   * float32 in the binary upload. When no documents have embeddings, the server
   * generates embeddings in batches (dimension=0 flow).
   *
   * Mixed documents (some with embeddings, some without) are rejected.
   *
   * @param indexName - Name of the index to create.
   * @param docs - Documents, optionally with pre-computed embeddings.
   * @param options - Optional model ID and progress callback.
   * @returns Promise that resolves to MutationResult when the index is ready.
   * @throws {Error} If the index already exists or creation fails.
   *
   * @example
   * ```typescript
   * const result = await client.createIndex('knowledge-base', [
   *   { id: 'doc1', text: 'Introduction to AI' },
   *   { id: 'doc2', text: 'Machine learning basics' }
   * ], {
   *   onProgress: (p) => console.log(`${p.status} ${p.progress}%`),
   * });
   * ```
   */
  async createIndex(
    indexName: string,
    docs: DocumentInfo[],
    options?: CreateIndexOptions,
  ): Promise<MutationResult> {
    let resolvedModelId: string;
    if (options?.modelId !== undefined) {
      resolvedModelId = options.modelId;
    } else {
      const hasEmbeddings = docs.some(
        (doc) => Array.isArray(doc.embedding) && doc.embedding.length > 0,
      );
      resolvedModelId = hasEmbeddings ? "custom" : DEFAULT_MODEL_ID;
    }
    return this.#internal.createIndex(indexName, docs, resolvedModelId, options);
  }

  /**
   * Gets information about a specific index.
   *
   * @param indexName - Name of the index to retrieve.
   * @returns Promise that resolves to IndexInfo object.
   * @throws {Error} If the index does not exist.
   *
   * @example
   * ```typescript
   * const info = await client.getIndex('knowledge-base');
   * console.log(`Index has ${info.docCount} documents`);
   * ```
   */
  async getIndex(indexName: string): Promise<IndexInfo> {
    return this.#internal.getIndex(indexName);
  }

  /**
   * Lists all available indexes.
   *
   * @returns Promise that resolves to array of IndexInfo objects.
   *
   * @example
   * ```typescript
   * const indexes = await client.listIndexes();
   * indexes.forEach(index => {
   *   console.log(`${index.name}: ${index.docCount} docs`);
   * });
   * ```
   */
  async listIndexes(): Promise<IndexInfo[]> {
    return this.#internal.listIndexes();
  }

  /**
   * Deletes an index and all its data.
   *
   * @param indexName - Name of the index to delete.
   * @returns Promise that resolves to true if successful.
   * @throws {Error} If the index does not exist.
   *
   * @example
   * ```typescript
   * const deleted = await client.deleteIndex('old-index');
   * ```
   */
  async deleteIndex(indexName: string): Promise<boolean> {
    return this.#internal.deleteIndex(indexName);
  }


  /**
   * Adds or updates documents in an index asynchronously.
   *
   * The index rebuild happens server-side. This method polls until
   * the rebuild is complete and then returns.
   *
   * @param indexName - Name of the target index.
   * @param docs - Documents to add or update.
   * @param options - Optional configuration (upsert, onProgress callback).
   * @returns Promise that resolves to MutationResult when the operation is complete.
   * @throws {Error} If the index does not exist.
   *
   * @example
   * ```typescript
   * const result = await client.addDocs('knowledge-base', [
   *   { id: 'new-doc', text: 'New content to index' }
   * ], { upsert: true });
   * console.log(`Job ${result.jobId} completed`);
   * ```
   */
  async addDocs(
    indexName: string,
    docs: DocumentInfo[],
    options?: MutationOptions,
  ): Promise<MutationResult> {
    return this.#internal.addDocs(indexName, docs, options);
  }

  /**
   * Deletes documents from an index by their IDs asynchronously.
   *
   * The index rebuild happens server-side. This method polls until
   * the rebuild is complete and then returns.
   *
   * @param indexName - Name of the target index.
   * @param docIds - Array of document IDs to delete.
   * @param options - Optional configuration (onProgress callback).
   * @returns Promise that resolves to MutationResult when the operation is complete.
   * @throws {Error} If the index does not exist.
   *
   * @example
   * ```typescript
   * const result = await client.deleteDocs('knowledge-base', ['doc1', 'doc2']);
   * console.log(`Job ${result.jobId} completed`);
   * ```
   */
  async deleteDocs(
    indexName: string,
    docIds: string[],
    options?: MutationOptions,
  ): Promise<MutationResult> {
    return this.#internal.deleteDocs(indexName, docIds, options);
  }


  /**
   * Gets the current status of an async job.
   *
   * @param jobId - The job ID returned by createIndex, addDocs, or deleteDocs.
   * @returns Promise that resolves to JobStatusResponse with progress details.
   *
   * @example
   * ```typescript
   * const status = await client.getJobStatus(jobId);
   * console.log(`${status.status} — ${status.progress}%`);
   * ```
   */
  async getJobStatus(jobId: string): Promise<JobStatusResponse> {
    return this.#internal.getJobStatus(jobId);
  }


  /**
   * Retrieves documents from an index.
   *
   * @param indexName - Name of the target index.
   * @param options - Optional configuration for retrieval.
   * @returns Promise that resolves to array of documents.
   * @throws {Error} If the index does not exist.
   *
   * @example
   * ```typescript
   * // Get all documents
   * const allDocs = await client.getDocs('knowledge-base');
   *
   * // Get specific documents
   * const specificDocs = await client.getDocs('knowledge-base', {
   *   docIds: ['doc1', 'doc2']
   * });
   * ```
   */
  async getDocs(
    indexName: string,
    options?: GetDocumentsOptions,
  ): Promise<DocumentInfo[]> {
    return this.#internal.getDocs(indexName, options);
  }


  /**
   * Downloads an index from the cloud into memory for fast local querying.
   *
   * **How it works:**
   * 1. Fetches the index assets from the cloud
   * 2. Loads the embedding model for generating query embeddings
   * 3. Executes a local similarity match between the query embedding and the retrieved index.
   *
   * **Why use this?**
   * - Without `loadIndex()`: Every `query()` call goes to the cloud API (~100-500ms network latency)
   * - With `loadIndex()`: Queries run entirely in-memory (~1-10ms)
   *
   * **Reload behavior:**
   * If the index is already loaded, calling `loadIndex()` again will:
   * - Stop any existing auto-refresh polling
   * - Download a fresh copy from the cloud
   * - Replace the in-memory index
   *
   * **Auto-refresh (optional):**
   * Enable `autoRefresh: true` to periodically poll the cloud for updates.
   * When a newer version is detected, the index is automatically hot-swapped
   * without interrupting queries.
   *
   * @param indexName - Name of the index to load.
   * @param options - Optional configuration including auto-refresh settings.
   * @returns Promise that resolves to the index name.
   * @throws {Error} If the index does not exist in the cloud or loading fails.
   *
   * @example
   * ```typescript
   * // Simple load - enables fast local queries
   * await client.loadIndex('my-index');
   *
   * // Now queries run locally (fast, no network calls)
   * const results = await client.query('my-index', 'search text');
   *
   * // Load with auto-refresh to keep index up-to-date
   * await client.loadIndex('my-index', {
   *   autoRefresh: true,
   *   pollingIntervalInSeconds: 300, // Check cloud every 5 minutes
   * });
   *
   * // Stop auto-refresh by reloading without the option
   * await client.loadIndex('my-index');
   * ```
   */
  async loadIndex(indexName: string, options?: LoadIndexOptions): Promise<string> {
    return this.#internal.loadIndex(indexName, options);
  }

  /**
   * Performs a semantic similarity search against the specified index.
   *
   * If the index has been loaded via `loadIndex()`, runs entirely in-memory.
   * Otherwise, falls back to the cloud `/query` endpoint.
   *
   * @param indexName - Name of the target index to search.
   * @param query - The search query text.
   * @param options - Optional query configuration including topK (default: 5) and embedding overrides.
   * @returns Promise that resolves to SearchResult with matching documents.
   * @throws {Error} If the specified index does not exist.
   *
   * @example
   * ```typescript
   * const results = await client.query('knowledge-base', 'machine learning');
   * results.docs.forEach(doc => {
   *   console.log(`${doc.id}: ${doc.text} (score: ${doc.score})`);
   * });
   * ```
   */
  async query(
    indexName: string,
    query: string,
    options?: QueryOptions,
  ): Promise<SearchResult> {
    return this.#internal.query(indexName, query, options);
  }

}

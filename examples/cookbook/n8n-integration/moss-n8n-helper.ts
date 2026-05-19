import { MossClient } from '@moss-dev/moss';


// Moss N8N Helper - Wrapper around Moss SDK for use in n8n workflows
// This helper provides easy-to-use functions for the four core Moss operations:
// - createIndex: Bootstrap a new index from documents
// - addDocs: Upsert documents into an index
// - deleteDocs: Remove documents by ID
// - query: Run semantic/hybrid search queries
type MossDocumentInput = {
    id: string;
    text: string;
    metadata?: Record<string, any>;
    embedding?: number[];
};

/**
 * MossN8NHelper - Wrapper for Moss SDK optimized for n8n usage
 */
export class MossN8NHelper {
  private client: MossClient;

  /**
   * Initialize the Moss client
   * @param projectId - Your Moss project identifier
   * @param projectKey - Your Moss project authentication key
   */
  constructor(projectId: string, projectKey: string) {
    this.client = new MossClient(projectId, projectKey);
  }

  /**
   * Create a new index with documents
   * @param indexName - Name of the index to create
   * @param docs - Array of documents (each with id and text, optionally with metadata and embedding)
   * @param options - Optional configuration (modelId, onProgress callback)
   * @returns Promise resolving to the creation result with job info
   */
  
  
  async createIndex(
    indexName: string,
    docs: MossDocumentInput[],
    options?: {
      modelId?: string;
      onProgress?: (jobProgress: { status: string; progress: number; currentPhase?: string }) => void;
    }
  ): Promise<{
    jobId: string;
    indexName: string;
    docCount: number;
  }> {
    // Convert to Moss DocumentInfo format
    const mossDocs = docs.map(doc => ({
      id: doc.id,
      text: doc.text,
      ...(doc.metadata && { metadata: doc.metadata }),
      ...((doc.embedding?.length ?? 0) > 0 && {
        embedding: doc.embedding
      })
    }));

    // Call the SDK method which returns MutationResult
    const result = await this.client.createIndex(indexName, mossDocs, options);
    
    // If there's a progress callback, we need to poll for status updates
    // But for simplicity in this helper, we'll just return the basic result
    // Users can call getJobStatus separately if they need progress tracking
    return {
      jobId: result.jobId,
      indexName: result.indexName,
      docCount: result.docCount
    };
  }

  /**
   * Add or update documents in an index
   * @param indexName - Name of the target index
   * @param docs - Array of documents to add/update
   * @param options - Optional configuration (upsert, onProgress callback)
   * @returns Promise resolving to the operation result with job info
   */
  async addDocs(
    indexName: string,
    docs: Array<{
      id: string;
      text: string;
      metadata?: Record<string, any>;
      embedding?: number[];
    }>,
    options?: {
      upsert?: boolean;
      onProgress?: (jobProgress: { status: string; progress: number; currentPhase?: string }) => void;
    }
  ): Promise<{
    jobId: string;
    indexName: string;
    docCount: number;
  }> {
    // Convert to Moss DocumentInfo format
    const mossDocs = docs.map((doc: {
      id: string;
      text: string;
      metadata?: Record<string, any>;
      embedding?: number[];
    }) => ({
      id: doc.id,
      text: doc.text,
      ...(doc.metadata && { metadata: doc.metadata }),
      ...((doc.embedding?.length ?? 0) > 0 && {
        embedding: doc.embedding
      })
    }));

    // Call the SDK method which returns MutationResult
    const result = await this.client.addDocs(indexName, mossDocs, options);
    
    // Return the basic result - users can call getJobStatus for progress
    return {
      jobId: result.jobId,
      indexName: result.indexName,
      docCount: result.docCount
    };
  }

  /**
   * Delete documents from an index by their IDs
   * @param indexName - Name of the target index
   * @param docIds - Array of document IDs to delete
   * @param options - Optional configuration (onProgress callback)
   * @returns Promise resolving to the deletion result with job info
   */
  async deleteDocs(
    indexName: string,
    docIds: string[],
    options?: {
      onProgress?: (jobProgress: { status: string; progress: number; currentPhase?: string }) => void;
    }
  ): Promise<{
    jobId: string;
    indexName: string;
    docCount: number;
  }> {
    // Call the SDK method which returns MutationResult
    const result = await this.client.deleteDocs(indexName, docIds, options);
    
    // Return the basic result - users can call getJobStatus for progress
    return {
      jobId: result.jobId,
      indexName: result.indexName,
      docCount: result.docCount
    };
  }

  /**
   * Query an index for semantic/hybrid search
   * @param indexName - Name of the index to query
   * @param queryText - The search query text
   * @param options - Optional query configuration (topK, etc.)
   * @returns Promise resolving to search results
   */
  async query(
    indexName: string,
    queryText: string,
    options?: {
      topK?: number;
    }
  ): Promise<Array<{
    id: string;
    text: string;
    metadata?: Record<string, any>;
    score: number;
  }>> {
    // Note: Per Moss SDK docs, query() will use local index if loaded via loadIndex(),
    // otherwise it falls back to cloud query. For best performance in n8n workflows,
    // users should call loadIndex() once before doing multiple queries.
    const results = await this.client.query(indexName, queryText, {
      topK: options?.topK ?? 10
    });

    // Convert to n8n-friendly format
    return results.docs.map(doc => ({
      id: doc.id,
      text: doc.text,
      ...(doc.metadata && { metadata: doc.metadata }),
      score: doc.score
    }));
  }

  /**
   * Load an index into memory for fast local querying
   * @param indexName - Name of the index to load
   * @param options - Optional configuration including auto-refresh settings
   * @returns Promise that resolves to index info
   */
  async loadIndex(
    indexName: string,
    options?: {
      autoRefresh?: boolean;
      pollingIntervalInSeconds?: number;
    }
  ): Promise<string> {
    return this.client.loadIndex(indexName, options);
  }

  /**
   * Get the status of an async job
   * @param jobId - The job ID from createIndex, addDocs, or deleteDocs
   * @returns Promise resolving to job status with progress details
   */
  async getJobStatus(jobId: string): Promise<{
    status: string;
    progress: number;
    currentPhase?: string;
    error?: string;
  }> {
    const status = await this.client.getJobStatus(jobId);
    return {
      status: status.status,
      progress: status.progress,
      currentPhase: status.currentPhase?.toString(),
      error: status.error ?? undefined
    };
  }

  /**
   * Close the client and release resources
   * Note: MossClient doesn't expose a public close()/dispose() API, so this is a no-op.
   * The helper remains usable after calling close().
   */
  close(): void {
    // No-op: do not invalidate `this.client` by nulling it out.
  }
}

// Example usage for n8n:
// const helper = new MossN8NHelper('your-project-id', 'your-project-key');
// 
// // Create index
// const createResult = await helper.createIndex('my-index', [
//   { id: '1', text: 'Hello world', metadata: { source: 'example' } }
// ]);
// 
// // Check creation status (optional)
// const createStatus = await helper.getJobStatus(createResult.jobId);
// 
// // Add docs
// const addResult = await helper.addDocs('my-index', [
//   { id: '2', text: 'Another document', metadata: { source: 'example' } }
// ]);
// 
// // Load index for fast local queries (recommended before querying)
// await helper.loadIndex('my-index');
// 
// // Query
// const results = await helper.query('my-index', 'hello', { topK: 5 });
// 
// // Delete docs
// const deleteResult = await helper.deleteDocs('my-index', ['1']);
// 
// // Clean up
// helper.close();
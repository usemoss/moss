import { MossClient } from '@moss-dev/moss';

// Moss N8N Helper - Wrapper around Moss SDK for use in n8n workflows
// This helper provides easy-to-use functions for the four core Moss operations:
// - createIndex: Bootstrap a new index from documents
// - addDocs: Upsert documents into an index
// - deleteDocs: Remove documents by ID
// - query: Run semantic/hybrid search queries

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
   * @returns Promise resolving to the creation result
   */
  async createIndex(
    indexName: string,
    docs: Array<{
      id: string;
      text: string;
      metadata?: Record<string, any>;
      embedding?: number[];
    }>,
    options?: {
      modelId?: string;
      onProgress?: (status: string, progress: number) => void;
    }
  ): Promise<{
    jobId: string;
    status: string;
    progress: number;
  }> {
    // Convert to Moss DocumentInfo format
    const mossDocs = docs.map(doc => ({
      id: doc.id,
      text: doc.text,
      ...(doc.metadata && { metadata: doc.metadata }),
      ...(doc.embedding && { embedding: doc.embedding })
    }));

    const result = await this.client.createIndex(indexName, mossDocs, options);
    return {
      jobId: result.jobId,
      status: result.status,
      progress: result.progress
    };
  }

  /**
   * Add or update documents in an index
   * @param indexName - Name of the target index
   * @param docs - Array of documents to add/update
   * @param options - Optional configuration (upsert, onProgress callback)
   * @returns Promise resolving to the operation result
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
      onProgress?: (status: string, progress: number) => void;
    }
  ): Promise<{
    jobId: string;
    status: string;
    progress: number;
  }> {
    // Convert to Moss DocumentInfo format
    const mossDocs = docs.map(doc => ({
      id: doc.id,
      text: doc.text,
      ...(doc.metadata && { metadata: doc.metadata }),
      ...(doc.embedding && { embedding: doc.embedding })
    }));

    const result = await this.client.addDocs(indexName, mossDocs, options);
    return {
      jobId: result.jobId,
      status: result.status,
      progress: result.progress
    };
  }

  /**
   * Delete documents from an index by their IDs
   * @param indexName - Name of the target index
   * @param docIds - Array of document IDs to delete
   * @param options - Optional configuration (onProgress callback)
   * @returns Promise resolving to the deletion result
   */
  async deleteDocs(
    indexName: string,
    docIds: string[],
    options?: {
      onProgress?: (status: string, progress: number) => void;
    }
  ): Promise<{
    jobId: string;
    status: string;
    progress: number;
  }> {
    const result = await this.client.deleteDocs(indexName, docIds, options);
    return {
      jobId: result.jobId,
      status: result.status,
      progress: result.progress
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
    // Load index for fast local queries (recommended for n8n workflows)
    await this.client.loadIndex(indexName);
    
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
   * Get the status of an async job
   * @param jobId - The job ID from createIndex, addDocs, or deleteDocs
   * @returns Promise resolving to job status
   */
  async getJobStatus(jobId: string): Promise<{
    status: string;
    progress: number;
  }> {
    const status = await this.client.getJobStatus(jobId);
    return {
      status: status.status,
      progress: status.progress
    };
  }

  /**
   * Dispose of the client resources
   */
  dispose(): void {
    this.client.dispose();
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
// // Add docs
// await helper.addDocs('my-index', [
//   { id: '2', text: 'Another document', metadata: { source: 'example' } }
// ]);
// 
// // Query
// const results = await helper.query('my-index', 'hello');
// 
// // Delete docs
// await helper.deleteDocs('my-index', ['1']);
// 
// helper.dispose();
import {
  LoadIndexOptions,
  CreateIndexOptions,
  MutationOptions,
  MossModel,
  QueryOptions as SdkQueryOptions,
} from "../models";
import { JobStatus } from "@moss-dev/moss-core";
import type {
  DocumentInfo,
  GetDocumentsOptions,
  IndexInfo,
  SearchResult,
  JobStatusResponse,
  MutationResult,
} from "@moss-dev/moss-core";
import * as MossCore from "@moss-dev/moss-core";
import { CLOUD_API_MANAGE_URL, CLOUD_QUERY_URL } from "../constants";
import { CloudApiClient } from "../utils/cloudApiClient";

/**
 * Internal client — mutations go through Rust ManageClient,
 * local queries go through Rust IndexManager (including embedding generation).
 * Cloud fallback queries go through the HTTP CloudApiClient.
 */
export class InternalMossClient {
  private readonly cloudClient: CloudApiClient;
  private readonly manageClient: {
    createIndex(name: string, docs: DocumentInfo[], modelId: string, onProgress?: ((...args: any[]) => void) | null): Promise<MutationResult>;
    addDocs(name: string, docs: DocumentInfo[], options?: MutationOptions | null, onProgress?: ((...args: any[]) => void) | null): Promise<MutationResult>;
    deleteDocs(name: string, docIds: string[], onProgress?: ((...args: any[]) => void) | null): Promise<MutationResult>;
    getJobStatus(jobId: string): Promise<JobStatusResponse>;
    getIndex(name: string): Promise<IndexInfo>;
    listIndexes(): Promise<IndexInfo[]>;
    deleteIndex(name: string): Promise<boolean>;
    getDocs(name: string, options?: GetDocumentsOptions | null): Promise<DocumentInfo[]>;
  };
  private readonly indexManager: {
    loadIndex(indexName: string, options?: LoadIndexOptions | null): Promise<IndexInfo>;
    unloadIndex(indexName: string): Promise<void>;
    hasIndex(indexName: string): Promise<boolean>;
    query(
      indexName: string,
      query: string,
      queryEmbedding: number[],
      topK?: number,
      alpha?: number,
      filter?: Record<string, unknown>,
    ): Promise<SearchResult>;
    queryText(
      indexName: string,
      query: string,
      topK?: number,
      alpha?: number,
      filter?: Record<string, unknown>,
    ): Promise<SearchResult>;
    loadQueryModel(indexName: string): Promise<void>;
    refreshIndex(indexName: string): Promise<{ indexName: string; previousUpdatedAt: string; newUpdatedAt: string; wasUpdated: boolean }>;
    getIndexInfo(indexName: string): Promise<IndexInfo>;
  };

  constructor(projectId: string, projectKey: string) {
    this.cloudClient = new CloudApiClient(projectId, projectKey, CLOUD_API_MANAGE_URL, CLOUD_QUERY_URL);
    const runtime = MossCore as unknown as {
      ManageClient?: new (projectId: string, projectKey: string, baseUrl?: string | null) => InternalMossClient["manageClient"];
      IndexManager?: new (projectId: string, projectKey: string, baseUrl?: string | null) => InternalMossClient["indexManager"];
      default?: {
        ManageClient?: new (projectId: string, projectKey: string, baseUrl?: string | null) => InternalMossClient["manageClient"];
        IndexManager?: new (projectId: string, projectKey: string, baseUrl?: string | null) => InternalMossClient["indexManager"];
      };
    };
    const ManageClientCtor = runtime.ManageClient ?? runtime.default?.ManageClient;
    const IndexManagerCtor = runtime.IndexManager ?? runtime.default?.IndexManager;
    if (!ManageClientCtor || !IndexManagerCtor) {
      throw new Error("moss-core runtime is missing ManageClient/IndexManager exports");
    }
    this.manageClient = new ManageClientCtor(projectId, projectKey);
    this.indexManager = new IndexManagerCtor(projectId, projectKey);
  }

  /**
   * Wrap an onProgress callback to adapt NAPI-RS ThreadsafeFunction's
   * Node.js (err, value) callback convention into a single-arg (value) callback.
   */
  private wrapProgress(
    onProgress?: (progress: any) => void,
  ): ((_err: any, progress: any) => void) | undefined {
    if (!onProgress) return undefined;
    return (_err: any, progress: any) => onProgress(progress);
  }

  /**
   * Normalize runtime status values from Rust/core to SDK canonical lowercase format.
   */
  private normalizeJobStatus(status: string): JobStatus {
    const normalized = status.trim().toLowerCase().replace(/\s+/g, "_");
    const compact = normalized.replace(/_/g, "");

    if (normalized === "pending_upload" || compact === "pendingupload") {
      return JobStatus.PendingUpload;
    }
    if (normalized === "uploading") {
      return JobStatus.Uploading;
    }
    if (normalized === "building") {
      return JobStatus.Building;
    }
    if (normalized === "completed") {
      return JobStatus.Completed;
    }
    if (normalized === "failed") {
      return JobStatus.Failed;
    }

    throw new Error(`Unsupported job status '${status}' returned by moss-core`);
  }

  async createIndex(
    indexName: string,
    docs: DocumentInfo[],
    modelId: string,
    options?: CreateIndexOptions,
  ): Promise<MutationResult> {
    if (!docs.length) {
      throw new Error("createIndex requires at least one document");
    }
    const result = await this.manageClient.createIndex(
      indexName,
      docs,
      modelId,
      this.wrapProgress(options?.onProgress),
    );
    return result as MutationResult;
  }

  async addDocs(
    indexName: string,
    docs: DocumentInfo[],
    options?: MutationOptions,
  ): Promise<MutationResult> {
    if (Array.isArray(docs) && docs.length === 0) {
      throw new Error("addDocs requires at least one document");
    }
    const result = await this.manageClient.addDocs(
      indexName,
      docs,
      options ?? null,
      this.wrapProgress(options?.onProgress),
    );
    return result as MutationResult;
  }

  async deleteDocs(
    indexName: string,
    docIds: string[],
    options?: MutationOptions,
  ): Promise<MutationResult> {
    if (Array.isArray(docIds) && docIds.length === 0) {
      throw new Error("deleteDocs requires at least one document ID");
    }
    const result = await this.manageClient.deleteDocs(
      indexName,
      docIds,
      this.wrapProgress(options?.onProgress),
    );
    return result as MutationResult;
  }

  async getJobStatus(jobId: string): Promise<JobStatusResponse> {
    const response = (await this.manageClient.getJobStatus(jobId)) as JobStatusResponse;
    return {
      ...response,
      status: this.normalizeJobStatus(response.status),
      currentPhase: (response.currentPhase ?? null) as any,
      error: (response.error ?? null) as any,
    };
  }

  async getIndex(indexName: string): Promise<IndexInfo> {
    return this.manageClient.getIndex(indexName);
  }

  async listIndexes(): Promise<IndexInfo[]> {
    return this.manageClient.listIndexes();
  }

  async deleteIndex(indexName: string): Promise<boolean> {
    return this.manageClient.deleteIndex(indexName);
  }

  async getDocs(
    indexName: string,
    options?: GetDocumentsOptions,
  ): Promise<DocumentInfo[]> {
    return this.manageClient.getDocs(indexName, options ?? null);
  }

  async loadIndex(
    indexName: string,
    options?: LoadIndexOptions,
  ): Promise<string> {
    const info = await this.indexManager.loadIndex(indexName, options ?? null);
    const modelId = info.model.id as MossModel;
    if (modelId !== "custom") {
      await this.indexManager.loadQueryModel(indexName);
    }
    return info.name;
  }

  async query(
    indexName: string,
    query: string,
    options?: SdkQueryOptions,
  ): Promise<SearchResult> {
    if (await this.indexManager.hasIndex(indexName)) {
      const topK = options?.topK ?? 5;
      const alpha = options?.alpha ?? 0.8;

      if (options?.embedding) {
        return this.indexManager.query(indexName, query, options.embedding, topK, alpha, options?.filter);
      }

      return this.indexManager.queryText(indexName, query, topK, alpha, options?.filter);
    }

    const topK = options?.topK ?? 5;
    const queryEmbedding = options?.embedding;
    return this.cloudClient.makeQueryRequest<SearchResult>(
      indexName,
      query,
      topK,
      queryEmbedding,
    );
  }
}

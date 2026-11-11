/// <reference lib="esnext.disposable" preserve="true" />
/**
 * Moss Semantic Search SDK
 *
 * Powerful TypeScript SDK for local semantic search using state-of-the-art embedding models.
 *
 * @example
 * ```typescript
 * import { MossClient } from '@moss-js/moss';
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
export { SessionIndex } from "./client/sessionIndex";
export { ManageApiError } from "./utils/manageHttp";
export { isMossError } from "./errors";
export type { MossError, MossErrorCode } from "./errors";
export type { IAuthenticator, AuthToken } from "./auth/authenticator.interface";

// Responses and browser tasks through the Moss inference gateway, in the shape of OpenAI's APIs
export { MossInference, inference } from "./inference";
export type { Responses, TaskFiles, Tasks } from "./inference";
export { ResponseStream } from "./inference/stream";
export { InferenceError } from "./inference/error";
export type { InferenceErrorType } from "./inference/error";
export type {
  EasyInputMessage,
  FunctionCallOutput,
  FunctionTool,
  InferenceRequestOptions,
  McpCall,
  McpServer,
  MossInferenceOptions,
  Response,
  ResponseCreateParams,
  ResponseCreateParamsBase,
  ResponseCreateParamsNonStreaming,
  ResponseCreateParamsStreaming,
  ResponseFunctionToolCall,
  ResponseInputItem,
  ResponseOutputItem,
  ResponseReasoningItem,
  ResponseOutputMessage,
  ResponseOutputText,
  ResponseStreamEvent,
  ResponseUsage,
  Task,
  TaskCreateOptions,
  TaskCreateParams,
  TaskEnvironment,
  TaskError,
  TaskFile,
  TaskFileContent,
  TaskFileList,
  TaskLimits,
  TaskRequestOptions,
  TaskResult,
  TaskRunOptions,
  TaskStatus,
  TaskUsage,
  TaskVerification,
  TaskWaitOptions,
} from "./inference/types";

// SDK-specific types
export type {
  ISODate,
  ModelArtifactIdentity,
  MossIdentity,
  MossModel,
  CreateIndexOptions,
  ParseFileInput,
  ParseOptions,
  CreateIndexFromFilesOptions,
  WebSource,
  WebSourceStatus,
  WebSourceRefreshCadence,
  CreateWebSourceResult,
  CreateWebSourceOptions,
  UpdateWebSourceResult,
  UpdateWebSourceOptions,
  ResyncWebSourceResult,
  DeleteWebSourceResult,
} from "./models";

// Status values ship as plain objects, so a file transpiled on its own can read their members
export { IndexStatus, JobStatus, JobPhase } from "./models";

// Re-export moss-core types directly
export type {
  IndexInfo,
  ModelRef,
  DocumentInfo,
  QueryResultDocumentInfo,
  SearchResult,
  QueryOptions,
  GetDocumentsOptions,
  MutationResult,
  RefreshResult,
  JobStatusResponse,
  PushIndexResult,
  LoadSessionOptions,
  LoadFromDiskOptions,
  SnapshotInfo,
} from "@moss-js/moss-core";

// SDK-specific types (extended or unique to SDK)
export type {
  LoadIndexOptions,
  LoadIndexesResult,
  MossClientOptions,
  MutationOptions,
  JobProgress,
} from "./models";

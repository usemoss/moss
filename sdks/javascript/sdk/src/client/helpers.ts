import { JobProgress, GetJobStatusResponse, HandleGetJobStatusOptions } from "../models";
import type { DocumentInfo, MutationResult } from "@moss-dev/moss-core";
import { CloudApiClient } from "../utils/cloudApiClient";

/**
 * Returns the shared embedding dimension, 0 if text-only, or throws on mixed/mismatched.
 */
export function resolveEmbeddingDimension(
  docs: DocumentInfo[],
  modelId: string,
): number {
  const hasEmb = (doc: DocumentInfo) =>
    Array.isArray(doc.embedding) && doc.embedding.length > 0;

  const withCount = docs.filter(hasEmb).length;
  const withoutCount = docs.length - withCount;

  if (withCount > 0 && withoutCount > 0) {
    throw new Error(
      "All documents must either all have embeddings or none should have embeddings",
    );
  }

  // Text-only: server will generate embeddings
  if (withCount === 0) {
    if (modelId === "custom") {
      throw new Error(
        "Cannot use model 'custom' without pre-computed embeddings. " +
          "Provide embeddings for all documents or use a built-in model like 'moss-minilm'.",
      );
    }
    return 0;
  }

  // All docs have embeddings — validate consistent dimension
  const dimension = docs[0].embedding!.length;
  for (let i = 1; i < docs.length; i++) {
    if (docs[i].embedding!.length !== dimension) {
      throw new Error(
        `Document "${docs[i].id}" has mismatched embedding dimension ` +
          `(expected ${dimension}, got ${docs[i].embedding!.length})`,
      );
    }
  }

  return dimension;
}

/**
 * Serializes docs into the bulk upload binary format:
 *   [MOSS (4B)] [version=1 (4B)] [docCount (4B)] [dim (4B)]
 *   [metaLen (4B)] [metadata JSON] [float32 embeddings]
 */
export function serializeBulkPayload(
  docs: DocumentInfo[],
  dimension: number,
): ArrayBuffer {
  const metadata = docs.map(({ embedding: _embedding, ...rest }) => rest);
  const metadataBytes = new TextEncoder().encode(JSON.stringify(metadata));

  const HEADER_SIZE = 20;
  const embeddingsSize = dimension > 0 ? docs.length * dimension * 4 : 0;
  const totalSize = HEADER_SIZE + metadataBytes.length + embeddingsSize;

  const buffer = new ArrayBuffer(totalSize);
  const view = new DataView(buffer);
  const byteView = new Uint8Array(buffer);

  byteView.set([0x4d, 0x4f, 0x53, 0x53], 0); // "MOSS"
  view.setUint32(4, 1, true);                  // bulk format version
  view.setUint32(8, docs.length, true);        // doc count
  view.setUint32(12, dimension, true);         // embedding dimension
  view.setUint32(16, metadataBytes.length, true);

  byteView.set(metadataBytes, HEADER_SIZE);

  if (dimension > 0) {
    const embOffset = HEADER_SIZE + metadataBytes.length;
    const floatView = new Float32Array(docs.length * dimension);
    for (let i = 0; i < docs.length; i++) {
      const emb = docs[i].embedding!;
      for (let d = 0; d < dimension; d++) {
        floatView[i * dimension + d] = emb[d];
      }
    }
    byteView.set(new Uint8Array(floatView.buffer), embOffset);
  }

  return buffer;
}

const MAX_UPLOAD_RETRIES = 3;
const BASE_DELAY_MS = 1_000;
const UPLOAD_TIMEOUT_MS = 1_800_000; // 30 minutes

/** PUT payload to presigned URL with exponential backoff on 5xx. 4xx fails immediately. */
export async function uploadWithRetries(
  uploadUrl: string,
  payload: ArrayBuffer,
): Promise<void> {
  let lastResponse: Response | undefined;

  for (let attempt = 0; attempt < MAX_UPLOAD_RETRIES; attempt++) {
    lastResponse = await fetch(uploadUrl, {
      method: "PUT",
      body: payload,
      headers: { "Content-Type": "application/octet-stream" },
      signal: AbortSignal.timeout(UPLOAD_TIMEOUT_MS),
    });

    if (lastResponse.ok) return;

    if (lastResponse.status < 500) break; // 4xx not retryable
    if (attempt === MAX_UPLOAD_RETRIES - 1) break;

    const delay = BASE_DELAY_MS * Math.pow(2, attempt); // 1s, 2s, 4s
    console.warn(
      `[moss] Upload attempt ${attempt + 1}/${MAX_UPLOAD_RETRIES} failed ` +
        `with ${lastResponse.status}, retrying in ${delay}ms...`,
    );
    await new Promise((resolve) => setTimeout(resolve, delay));
  }

  throw new Error(
    `Failed to upload bulk data: ${lastResponse!.status} ${lastResponse!.statusText}`,
  );
}

const POLL_INTERVAL_MS = 2_000;
const MAX_POLL_TIME_MS = 30 * 60 * 1_000; // 30 minutes
const MAX_CONSECUTIVE_ERRORS = 3;

/** Polls job until completed/failed. 30min timeout, 3 consecutive error limit. */
export async function pollJobUntilComplete(
  cloudClient: CloudApiClient,
  jobId: string,
  indexName: string,
  docCount: number,
  onProgress?: (progress: JobProgress) => void,
): Promise<MutationResult> {
  const start = Date.now();
  let consecutiveErrors = 0;

  while (Date.now() - start < MAX_POLL_TIME_MS) {
    let status: GetJobStatusResponse;

    try {
      status = await cloudClient.makeRequest<
        GetJobStatusResponse,
        HandleGetJobStatusOptions
      >("getJobStatus", { jobId });
      consecutiveErrors = 0;
    } catch (error) {
      consecutiveErrors++;
      if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
        throw new Error(
          `Job status polling failed after ${MAX_CONSECUTIVE_ERRORS} consecutive errors: ` +
            `${error instanceof Error ? error.message : String(error)}`,
        );
      }
      await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
      continue;
    }

    onProgress?.({
      jobId,
      status: status.status,
      progress: status.progress,
      currentPhase: status.currentPhase,
    });

    if (status.status === "completed") {
      return { jobId, indexName, docCount };
    }

    if (status.status === "failed") {
      throw new Error(
        `Job failed: ${status.error ?? "unknown error"}`,
      );
    }

    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }

  throw new Error(
    `Job timed out after ${MAX_POLL_TIME_MS / 1_000}s (job ${jobId})`,
  );
}

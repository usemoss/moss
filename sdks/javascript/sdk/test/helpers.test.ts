/**
 * Unit tests for helpers.ts — pure functions and utility helpers.
 *
 * resolveEmbeddingDimension and serializeBulkPayload are pure (no mocking).
 * uploadWithRetries needs global fetch mocked.
 * pollJobUntilComplete takes a CloudApiClient instance param (pass a mock object).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import type {
  DocumentInfo,
  JobProgress,
  MutationResult,
  GetJobStatusResponse,
} from "../src/models";

import {
  resolveEmbeddingDimension,
  serializeBulkPayload,
  uploadWithRetries,
  pollJobUntilComplete,
} from "../src/client/helpers";

function makeDoc(
  id: string,
  text: string,
  embedding?: number[],
  metadata?: Record<string, string>,
): DocumentInfo {
  return { id, text, embedding, metadata };
}

function decodeHeader(buf: ArrayBuffer) {
  const view = new DataView(buf);
  const magic = new TextDecoder().decode(new Uint8Array(buf, 0, 4));
  const version = view.getUint32(4, true);
  const docCount = view.getUint32(8, true);
  const dimension = view.getUint32(12, true);
  const metadataLen = view.getUint32(16, true);
  return { magic, version, docCount, dimension, metadataLen };
}

function decodeMetadata(buf: ArrayBuffer): any[] {
  const view = new DataView(buf);
  const metadataLen = view.getUint32(16, true);
  const metadataBytes = new Uint8Array(buf, 20, metadataLen);
  return JSON.parse(new TextDecoder().decode(metadataBytes));
}

function decodeEmbeddings(buf: ArrayBuffer): number[] {
  const view = new DataView(buf);
  const docCount = view.getUint32(8, true);
  const dimension = view.getUint32(12, true);
  const metadataLen = view.getUint32(16, true);
  const embOffset = 20 + metadataLen;
  const floatCount = docCount * dimension;
  const result: number[] = [];
  for (let i = 0; i < floatCount; i++) {
    result.push(view.getFloat32(embOffset + i * 4, true));
  }
  return result;
}

describe("resolveEmbeddingDimension", () => {
  it("should return dimension when all docs have same-dimension embeddings", () => {
    const docs = [
      makeDoc("d1", "a", [1, 2, 3]),
      makeDoc("d2", "b", [4, 5, 6]),
    ];
    expect(resolveEmbeddingDimension(docs, "custom")).toBe(3);
  });

  it("should return 0 when no docs have embeddings and modelId is not 'custom'", () => {
    const docs = [makeDoc("d1", "a"), makeDoc("d2", "b")];
    expect(resolveEmbeddingDimension(docs, "moss-minilm")).toBe(0);
  });

  it("should throw when modelId is 'custom' but no docs have embeddings", () => {
    const docs = [makeDoc("d1", "a")];
    expect(() => resolveEmbeddingDimension(docs, "custom")).toThrow(
      "Cannot use model 'custom'",
    );
  });

  it("should throw when docs have mixed embeddings (some with, some without)", () => {
    const docs = [
      makeDoc("d1", "a", [1, 2]),
      makeDoc("d2", "b"), // no embedding
    ];
    expect(() => resolveEmbeddingDimension(docs, "custom")).toThrow(
      "all have embeddings or none",
    );
  });

  it("should throw when docs have mismatched embedding dimensions", () => {
    const docs = [
      makeDoc("d1", "a", [1, 2, 3]),
      makeDoc("d2", "b", [4, 5]), // dimension 2 vs 3
    ];
    expect(() => resolveEmbeddingDimension(docs, "custom")).toThrow(
      "mismatched embedding dimension",
    );
  });

  it("should handle single doc with embeddings", () => {
    const docs = [makeDoc("d1", "a", [1, 2, 3, 4, 5])];
    expect(resolveEmbeddingDimension(docs, "custom")).toBe(5);
  });

  it("should treat docs with empty embedding arrays as 'no embedding'", () => {
    const docs = [makeDoc("d1", "a", [])];
    // empty array → hasEmb returns false → no embeddings
    expect(resolveEmbeddingDimension(docs, "moss-minilm")).toBe(0);
  });

  it("should treat docs with undefined embedding as 'no embedding'", () => {
    const docs = [{ id: "d1", text: "a", embedding: undefined }];
    expect(resolveEmbeddingDimension(docs, "moss-minilm")).toBe(0);
  });
});

describe("serializeBulkPayload", () => {
  it("should write MOSS magic bytes and version 1 in header", () => {
    const docs = [makeDoc("d1", "hello", [1.0, 2.0])];
    const buf = serializeBulkPayload(docs, 2);
    const header = decodeHeader(buf);
    expect(header.magic).toBe("MOSS");
    expect(header.version).toBe(1);
  });

  it("should encode correct docCount and dimension in header", () => {
    const docs = [
      makeDoc("d1", "a", [1, 2, 3]),
      makeDoc("d2", "b", [4, 5, 6]),
    ];
    const buf = serializeBulkPayload(docs, 3);
    const header = decodeHeader(buf);
    expect(header.docCount).toBe(2);
    expect(header.dimension).toBe(3);
  });

  it("should strip embedding field from metadata JSON", () => {
    const docs = [makeDoc("d1", "hello", [1.0, 2.0])];
    const buf = serializeBulkPayload(docs, 2);
    const metadata = decodeMetadata(buf);
    expect(metadata[0]).not.toHaveProperty("embedding");
  });

  it("should preserve id, text, and metadata in JSON block", () => {
    const docs = [makeDoc("d1", "hello", [1.0], { source: "wiki" })];
    const buf = serializeBulkPayload(docs, 1);
    const metadata = decodeMetadata(buf);
    expect(metadata[0]).toEqual({
      id: "d1",
      text: "hello",
      metadata: { source: "wiki" },
    });
  });

  it("should encode embeddings as flat float32 LE values", () => {
    const docs = [
      makeDoc("d1", "a", [1.0, 2.0]),
      makeDoc("d2", "b", [3.0, 4.0]),
    ];
    const buf = serializeBulkPayload(docs, 2);
    const floats = decodeEmbeddings(buf);
    expect(floats).toEqual([1.0, 2.0, 3.0, 4.0]);
  });

  it("should produce correct total size: 20 + metadataLen + docCount*dim*4", () => {
    const docs = [makeDoc("d1", "hi", [0.5, 1.5, 2.5])];
    const buf = serializeBulkPayload(docs, 3);
    const header = decodeHeader(buf);
    const expectedSize = 20 + header.metadataLen + 1 * 3 * 4;
    expect(buf.byteLength).toBe(expectedSize);
  });

  it("should write dimension=0 and no embeddings block for text-only docs", () => {
    const docs = [makeDoc("d1", "hello"), makeDoc("d2", "world")];
    const buf = serializeBulkPayload(docs, 0);
    const header = decodeHeader(buf);
    expect(header.dimension).toBe(0);
    expect(buf.byteLength).toBe(20 + header.metadataLen);
  });

  it("should handle unicode text correctly", () => {
    const docs = [makeDoc("d1", "こんにちは世界", [1.0])];
    const buf = serializeBulkPayload(docs, 1);
    const metadata = decodeMetadata(buf);
    expect(metadata[0].text).toBe("こんにちは世界");
  });

  it("should handle empty text", () => {
    const docs = [makeDoc("d1", "", [1.0])];
    const buf = serializeBulkPayload(docs, 1);
    const metadata = decodeMetadata(buf);
    expect(metadata[0].text).toBe("");
    expect(metadata[0].id).toBe("d1");
  });

  it("should handle high-dimensional embeddings (384d)", () => {
    const dim = 384;
    const embedding = Array.from({ length: dim }, (_, i) => i * 0.001);
    const docs = [makeDoc("d1", "text", embedding)];
    const buf = serializeBulkPayload(docs, dim);
    const header = decodeHeader(buf);
    expect(header.dimension).toBe(384);

    const decoded = decodeEmbeddings(buf);
    expect(decoded.length).toBe(384);
    expect(Math.abs(decoded[1] - 0.001)).toBeLessThan(0.0001);
  });

  it("should handle many docs (100+)", () => {
    const docs = Array.from({ length: 100 }, (_, i) =>
      makeDoc(`doc-${i}`, `text ${i}`, [i * 0.1, i * 0.2]),
    );
    const buf = serializeBulkPayload(docs, 2);
    const header = decodeHeader(buf);
    expect(header.docCount).toBe(100);
    expect(header.dimension).toBe(2);
    expect(decodeEmbeddings(buf).length).toBe(200);
  });
});

describe("uploadWithRetries", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("should succeed on first attempt when fetch returns ok", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 200, statusText: "OK" }),
    );

    const payload = new ArrayBuffer(8);
    await uploadWithRetries("https://r2.example.com/upload", payload);

    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("should send PUT with correct Content-Type header", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 200, statusText: "OK" }),
    );

    const payload = new ArrayBuffer(8);
    await uploadWithRetries("https://r2.example.com/upload", payload);

    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toBe("https://r2.example.com/upload");
    expect(init?.method).toBe("PUT");
    expect(init?.headers).toEqual({
      "Content-Type": "application/octet-stream",
    });
  });

  it("should fail immediately on 4xx error (no retry)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        statusText: "Forbidden",
      }),
    );

    const payload = new ArrayBuffer(8);
    await expect(
      uploadWithRetries("https://r2.example.com/upload", payload),
    ).rejects.toThrow("Failed to upload bulk data: 403");

    // Only 1 attempt — no retries for 4xx
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("should retry on 5xx error and succeed on retry", async () => {
    const mockFetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: false,
        status: 503,
        statusText: "Service Unavailable",
      })
      .mockResolvedValueOnce({ ok: true, status: 200, statusText: "OK" });

    vi.stubGlobal("fetch", mockFetch);

    const payload = new ArrayBuffer(8);
    const promise = uploadWithRetries(
      "https://r2.example.com/upload",
      payload,
    );

    // Advance past the 1s backoff delay
    await vi.advanceTimersByTimeAsync(1100);
    await promise;

    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  it("should retry up to 3 times on 5xx then throw", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
    });

    vi.stubGlobal("fetch", mockFetch);

    const payload = new ArrayBuffer(8);
    const promise = uploadWithRetries(
      "https://r2.example.com/upload",
      payload,
    );

    // Register the rejection handler before advancing timers
    const assertion = expect(promise).rejects.toThrow(
      "Failed to upload bulk data: 500",
    );

    // Advance through all backoff delays: 1s + 2s
    await vi.advanceTimersByTimeAsync(1100);
    await vi.advanceTimersByTimeAsync(2100);

    await assertion;
    expect(mockFetch).toHaveBeenCalledTimes(3);
  });

  it("should use exponential backoff delays: 1s, 2s", async () => {
    let callTimes: number[] = [];
    const mockFetch = vi
      .fn()
      .mockImplementation(async () => {
        callTimes.push(Date.now());
        return { ok: false, status: 500, statusText: "Internal Server Error" };
      });

    vi.stubGlobal("fetch", mockFetch);

    const payload = new ArrayBuffer(8);
    const promise = uploadWithRetries(
      "https://r2.example.com/upload",
      payload,
    );

    // Register the rejection handler before advancing timers
    const assertion = expect(promise).rejects.toThrow();

    // First call happens immediately
    await vi.advanceTimersByTimeAsync(0);
    expect(callTimes.length).toBe(1);

    // After ~1s (1000ms base * 2^0), second call
    await vi.advanceTimersByTimeAsync(1100);
    expect(callTimes.length).toBe(2);

    // After ~2s (1000ms base * 2^1), third call
    await vi.advanceTimersByTimeAsync(2100);
    expect(callTimes.length).toBe(3);

    await assertion;
  });
});

describe("pollJobUntilComplete", () => {
  let mockMakeRequest: ReturnType<typeof vi.fn>;
  let mockCloudClient: { makeRequest: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    mockMakeRequest = vi.fn();
    mockCloudClient = { makeRequest: mockMakeRequest };
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("should return MutationResult when status is 'completed' on first poll", async () => {
    mockMakeRequest.mockResolvedValueOnce({
      jobId: "job-1",
      status: "completed",
      progress: 100,
      currentPhase: null,
    } satisfies GetJobStatusResponse);

    const promise = pollJobUntilComplete(
      mockCloudClient as any,
      "job-1",
      "my-index",
      10,
    );

    await vi.advanceTimersByTimeAsync(100);
    const result = await promise;

    expect(result).toEqual({
      jobId: "job-1",
      indexName: "my-index",
      docCount: 10,
    } satisfies MutationResult);
  });

  it("should throw with error message when status is 'failed'", async () => {
    mockMakeRequest.mockResolvedValueOnce({
      jobId: "job-1",
      status: "failed",
      progress: 0,
      currentPhase: null,
      error: "out of memory",
    });

    await expect(
      pollJobUntilComplete(mockCloudClient as any, "job-1", "idx", 5),
    ).rejects.toThrow("out of memory");
  });

  it("should throw 'unknown error' when failed status has no error field", async () => {
    mockMakeRequest.mockResolvedValueOnce({
      jobId: "job-1",
      status: "failed",
      progress: 0,
      currentPhase: null,
    });

    await expect(
      pollJobUntilComplete(mockCloudClient as any, "job-1", "idx", 5),
    ).rejects.toThrow("unknown error");
  });

  it("should poll multiple times until completed", async () => {
    mockMakeRequest
      .mockResolvedValueOnce({
        status: "building",
        progress: 30,
        currentPhase: "building_index",
      })
      .mockResolvedValueOnce({
        status: "building",
        progress: 70,
        currentPhase: "uploading",
      })
      .mockResolvedValueOnce({
        status: "completed",
        progress: 100,
        currentPhase: null,
      });

    const promise = pollJobUntilComplete(
      mockCloudClient as any,
      "job-1",
      "idx",
      5,
    );

    // Each poll cycle is 2s
    for (let i = 0; i < 6; i++) {
      await vi.advanceTimersByTimeAsync(2100);
    }

    const result = await promise;
    expect(result.jobId).toBe("job-1");
    expect(mockMakeRequest).toHaveBeenCalledTimes(3);
  });

  it("should invoke onProgress callback with each poll status", async () => {
    mockMakeRequest
      .mockResolvedValueOnce({
        status: "building",
        progress: 50,
        currentPhase: "building_index",
      })
      .mockResolvedValueOnce({
        status: "completed",
        progress: 100,
        currentPhase: null,
      });

    const updates: JobProgress[] = [];
    const promise = pollJobUntilComplete(
      mockCloudClient as any,
      "job-1",
      "idx",
      5,
      (p) => updates.push({ ...p }),
    );

    for (let i = 0; i < 5; i++) {
      await vi.advanceTimersByTimeAsync(2100);
    }

    await promise;

    expect(updates.length).toBe(2);
    expect(updates[0].status).toBe("building");
    expect(updates[0].progress).toBe(50);
    expect(updates[0].currentPhase).toBe("building_index");
    expect(updates[0].jobId).toBe("job-1");
    expect(updates[1].status).toBe("completed");
    expect(updates[1].progress).toBe(100);
    expect(updates[1].currentPhase).toBeNull();
    expect(updates[1].jobId).toBe("job-1");
  });

  it("should tolerate up to 2 consecutive poll errors then succeed", async () => {
    let pollCount = 0;
    mockMakeRequest.mockImplementation(async () => {
      pollCount++;
      if (pollCount <= 2) throw new Error("network error");
      return { status: "completed", progress: 100, currentPhase: null };
    });

    const promise = pollJobUntilComplete(
      mockCloudClient as any,
      "job-1",
      "idx",
      5,
    );

    for (let i = 0; i < 12; i++) {
      await vi.advanceTimersByTimeAsync(2100);
    }

    const result = await promise;
    expect(result.jobId).toBe("job-1");
  });

  it("should throw after 3 consecutive poll errors", async () => {
    mockMakeRequest.mockRejectedValue(new Error("network error"));

    const promise = pollJobUntilComplete(
      mockCloudClient as any,
      "job-1",
      "idx",
      5,
    );

    // Register rejection handler before advancing timers to avoid unhandled rejection
    const assertion = expect(promise).rejects.toThrow(
      "3 consecutive errors",
    );

    // Error 1 (immediate) → sleep 2s → error 2 → sleep 2s → error 3 → throw
    await vi.advanceTimersByTimeAsync(2100);
    await vi.advanceTimersByTimeAsync(2100);

    await assertion;
  });

  it("should reset consecutive error count after a successful poll", async () => {
    let pollCount = 0;
    mockMakeRequest.mockImplementation(async () => {
      pollCount++;
      // Fail 2, succeed 1 (building), fail 2, then complete
      if (pollCount <= 2) throw new Error("err");
      if (pollCount === 3) {
        return { status: "building", progress: 50, currentPhase: "building_index" };
      }
      if (pollCount <= 5) throw new Error("err");
      return { status: "completed", progress: 100, currentPhase: null };
    });

    const promise = pollJobUntilComplete(
      mockCloudClient as any,
      "job-1",
      "idx",
      5,
    );

    for (let i = 0; i < 20; i++) {
      await vi.advanceTimersByTimeAsync(2100);
    }

    const result = await promise;
    expect(result.jobId).toBe("job-1");
  });

  it("should timeout after 30 minutes with descriptive error", async () => {
    // Always return "building" — never completes
    mockMakeRequest.mockResolvedValue({
      status: "building",
      progress: 50,
      currentPhase: "building_index",
    });

    const promise = pollJobUntilComplete(
      mockCloudClient as any,
      "job-1",
      "idx",
      5,
    );

    // Register rejection handler before advancing timers
    const assertion = expect(promise).rejects.toThrow("timed out");

    // Advance 31 minutes (timeout is 30 min)
    await vi.advanceTimersByTimeAsync(31 * 60 * 1000);

    await assertion;
  });
});

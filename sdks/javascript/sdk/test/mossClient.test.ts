import { beforeEach, describe, expect, it, vi } from "vitest";
import type { DocumentInfo } from "../src/models";
import { InternalMossClient } from "../src/client/internalMossClient";
import { MossClient } from "../src/client/mossClient";

function makeDoc(id: string, text: string, embedding?: number[]): DocumentInfo {
  return { id, text, embedding };
}

const mockMakeQueryRequest = vi.fn();
const mockManageCreateIndex = vi.fn();
const mockManageAddDocs = vi.fn();
const mockManageDeleteDocs = vi.fn();
const mockManageGetJobStatus = vi.fn();
const mockManageGetIndex = vi.fn();
const mockManageListIndexes = vi.fn();
const mockManageDeleteIndex = vi.fn();
const mockManageGetDocs = vi.fn();

const mockIndexLoadIndex = vi.fn();
const mockIndexHasIndex = vi.fn();
const mockIndexQuery = vi.fn();
const mockIndexQueryText = vi.fn();
const mockIndexLoadQueryModel = vi.fn();
const mockIndexGetIndexInfo = vi.fn();

vi.mock("../src/utils/cloudApiClient", () => ({
  CloudApiClient: vi.fn().mockImplementation(() => ({
    makeQueryRequest: mockMakeQueryRequest,
  })),
}));

vi.mock("@moss-dev/moss-core", () => ({
  ManageClient: vi.fn().mockImplementation(() => ({
    createIndex: mockManageCreateIndex,
    addDocs: mockManageAddDocs,
    deleteDocs: mockManageDeleteDocs,
    getJobStatus: mockManageGetJobStatus,
    getIndex: mockManageGetIndex,
    listIndexes: mockManageListIndexes,
    deleteIndex: mockManageDeleteIndex,
    getDocs: mockManageGetDocs,
  })),
  IndexManager: vi.fn().mockImplementation(() => ({
    loadIndex: mockIndexLoadIndex,
    unloadIndex: vi.fn(),
    hasIndex: mockIndexHasIndex,
    query: mockIndexQuery,
    queryText: mockIndexQueryText,
    loadQueryModel: mockIndexLoadQueryModel,
    refreshIndex: vi.fn(),
    getIndexInfo: mockIndexGetIndexInfo,
  })),
  JobStatus: {
    PendingUpload: "pending_upload",
    Uploading: "uploading",
    Building: "building",
    Completed: "completed",
    Failed: "failed",
  },
  JobPhase: {
    Downloading: "downloading",
    Deserializing: "deserializing",
    GeneratingEmbeddings: "generating_embeddings",
    BuildingIndex: "building_index",
    Uploading: "uploading",
    Cleanup: "cleanup",
  },
  MODEL_DOWNLOAD_URL: "https://cdn.example.com/models",
  CLOUD_API_MANAGE_URL: "https://service.example.com/v1/manage",
  SDK_VERSION_NUMBER: "1.0.0",
}));

beforeEach(() => {
  mockMakeQueryRequest.mockReset();
  mockManageCreateIndex.mockReset();
  mockManageAddDocs.mockReset();
  mockManageDeleteDocs.mockReset();
  mockManageGetJobStatus.mockReset();
  mockManageGetIndex.mockReset();
  mockManageListIndexes.mockReset();
  mockManageDeleteIndex.mockReset();
  mockManageGetDocs.mockReset();
  mockIndexLoadIndex.mockReset();
  mockIndexHasIndex.mockReset();
  mockIndexQuery.mockReset();
  mockIndexQueryText.mockReset();
  mockIndexLoadQueryModel.mockReset();
  mockIndexGetIndexInfo.mockReset();
});

describe("InternalMossClient", () => {
  it("createIndex delegates to ManageClient", async () => {
    mockManageCreateIndex.mockResolvedValueOnce({
      jobId: "job1",
      indexName: "idx",
      docCount: 2,
    });
    const client = new InternalMossClient("proj", "key");

    const result = await client.createIndex("idx", [makeDoc("d1", "hello")], "moss-minilm");

    expect(result).toEqual({ jobId: "job1", indexName: "idx", docCount: 2 });
    expect(mockManageCreateIndex).toHaveBeenCalledWith("idx", [makeDoc("d1", "hello")], "moss-minilm", undefined);
  });

  it("addDocs delegates to ManageClient", async () => {
    mockManageAddDocs.mockResolvedValueOnce({
      jobId: "add1",
      indexName: "idx",
      docCount: 1,
    });
    const client = new InternalMossClient("proj", "key");

    const result = await client.addDocs("idx", [makeDoc("d1", "hello")]);

    expect(result.jobId).toBe("add1");
    expect(mockManageAddDocs).toHaveBeenCalledWith("idx", [makeDoc("d1", "hello")], null, undefined);
  });

  it("deleteDocs delegates to ManageClient", async () => {
    mockManageDeleteDocs.mockResolvedValueOnce({
      jobId: "del1",
      indexName: "idx",
      docCount: 1,
    });
    const client = new InternalMossClient("proj", "key");

    const result = await client.deleteDocs("idx", ["d1"]);

    expect(result.jobId).toBe("del1");
    expect(mockManageDeleteDocs).toHaveBeenCalledWith("idx", ["d1"], undefined);
  });

  it("read operations delegate to ManageClient", async () => {
    mockManageGetIndex.mockResolvedValueOnce({ name: "idx" });
    mockManageListIndexes.mockResolvedValueOnce([{ name: "idx" }]);
    mockManageDeleteIndex.mockResolvedValueOnce(true);
    mockManageGetDocs.mockResolvedValueOnce([makeDoc("d1", "hello")]);

    const client = new InternalMossClient("proj", "key");

    await expect(client.getIndex("idx")).resolves.toEqual({ name: "idx" });
    await expect(client.listIndexes()).resolves.toEqual([{ name: "idx" }]);
    await expect(client.deleteIndex("idx")).resolves.toBe(true);
    await expect(client.getDocs("idx")).resolves.toEqual([makeDoc("d1", "hello")]);
  });

  it("loadIndex calls loadQueryModel for non-custom indexes", async () => {
    mockIndexLoadIndex.mockResolvedValueOnce({
      name: "idx",
      model: { id: "moss-minilm" },
    });
    mockIndexLoadQueryModel.mockResolvedValueOnce(undefined);
    const client = new InternalMossClient("proj", "key");

    await expect(client.loadIndex("idx")).resolves.toBe("idx");
    expect(mockIndexLoadQueryModel).toHaveBeenCalledWith("idx");
  });

  it("loadIndex skips loadQueryModel for custom indexes", async () => {
    mockIndexLoadIndex.mockResolvedValueOnce({
      name: "idx",
      model: { id: "custom" },
    });
    const client = new InternalMossClient("proj", "key");

    await expect(client.loadIndex("idx")).resolves.toBe("idx");
    expect(mockIndexLoadQueryModel).not.toHaveBeenCalled();
  });

  it("query uses queryText for local path when no embedding provided", async () => {
    mockIndexHasIndex.mockResolvedValueOnce(true);
    mockIndexQueryText.mockResolvedValueOnce({ docs: [{ id: "local" }] });
    const client = new InternalMossClient("proj", "key");

    const result = await client.query("idx", "hello");

    expect(result).toEqual({ docs: [{ id: "local" }] });
    expect(mockIndexQueryText).toHaveBeenCalledWith("idx", "hello", 5, 0.8, undefined);
    expect(mockIndexQuery).not.toHaveBeenCalled();
  });

  it("query uses query with embedding when embedding provided", async () => {
    mockIndexHasIndex.mockResolvedValueOnce(true);
    mockIndexQuery.mockResolvedValueOnce({ docs: [{ id: "local" }] });
    const client = new InternalMossClient("proj", "key");

    const result = await client.query("idx", "hello", { embedding: [0.1, 0.2, 0.3] });

    expect(result).toEqual({ docs: [{ id: "local" }] });
    expect(mockIndexQuery).toHaveBeenCalledWith("idx", "hello", [0.1, 0.2, 0.3], 5, 0.8, undefined);
    expect(mockIndexQueryText).not.toHaveBeenCalled();
  });

  it("query falls back to cloud path when not loaded", async () => {
    mockIndexHasIndex.mockResolvedValueOnce(false);
    mockMakeQueryRequest.mockResolvedValueOnce({ docs: [{ id: "cloud" }] });
    const client = new InternalMossClient("proj", "key");

    await expect(client.query("idx", "hello")).resolves.toEqual({
      docs: [{ id: "cloud" }],
    });
    expect(mockMakeQueryRequest).toHaveBeenCalledWith(
      "idx",
      "hello",
      5,
      undefined,
    );
  });
});

describe("MossClient", () => {
  it("createIndex model auto-detection matches current behavior", async () => {
    mockManageCreateIndex.mockResolvedValue({
      jobId: "job",
      indexName: "idx",
      docCount: 1,
    });
    const client = new MossClient("proj", "key");

    await client.createIndex("idx", [makeDoc("d1", "text", [1])]);
    expect(mockManageCreateIndex).toHaveBeenLastCalledWith(
      "idx",
      [makeDoc("d1", "text", [1])],
      "custom",
      undefined,
    );

    await client.createIndex("idx", [makeDoc("d2", "text", [])]);
    expect(mockManageCreateIndex).toHaveBeenLastCalledWith(
      "idx",
      [makeDoc("d2", "text", [])],
      "moss-minilm",
      undefined,
    );

    await client.createIndex("idx", [makeDoc("d3", "text")]);
    expect(mockManageCreateIndex).toHaveBeenLastCalledWith(
      "idx",
      [makeDoc("d3", "text")],
      "moss-minilm",
      undefined,
    );
  });

  it("delegates other public methods", async () => {
    mockManageAddDocs.mockResolvedValueOnce({ jobId: "a1", indexName: "idx", docCount: 1 });
    mockManageDeleteDocs.mockResolvedValueOnce({
      jobId: "d1",
      indexName: "idx",
      docCount: 1,
    });
    mockManageGetJobStatus.mockResolvedValueOnce({
      jobId: "job",
      status: "completed",
      progress: 100,
      currentPhase: null,
      createdAt: "",
      updatedAt: "",
      completedAt: "",
    });
    mockManageGetIndex.mockResolvedValueOnce({ name: "idx" });
    mockManageListIndexes.mockResolvedValueOnce([{ name: "idx" }]);
    mockManageDeleteIndex.mockResolvedValueOnce(true);
    mockManageGetDocs.mockResolvedValueOnce([makeDoc("d1", "hello")]);
    mockIndexHasIndex.mockResolvedValueOnce(true);
    mockIndexQueryText.mockResolvedValueOnce({ docs: [{ id: "q1" }] });
    mockIndexLoadIndex.mockResolvedValueOnce({ name: "idx", model: { id: "custom" } });

    const client = new MossClient("proj", "key");
    await expect(client.addDocs("idx", [makeDoc("d1", "x")])).resolves.toMatchObject({
      jobId: "a1",
    });
    await expect(client.deleteDocs("idx", ["d1"])).resolves.toMatchObject({
      jobId: "d1",
    });
    await expect(client.getJobStatus("job")).resolves.toMatchObject({
      status: "completed",
    });
    await expect(client.getIndex("idx")).resolves.toEqual({ name: "idx" });
    await expect(client.listIndexes()).resolves.toEqual([{ name: "idx" }]);
    await expect(client.deleteIndex("idx")).resolves.toBe(true);
    await expect(client.getDocs("idx")).resolves.toEqual([makeDoc("d1", "hello")]);
    await expect(
      client.query("idx", "hello"),
    ).resolves.toEqual({ docs: [{ id: "q1" }] });
    await expect(client.loadIndex("idx")).resolves.toBe("idx");
  });
});

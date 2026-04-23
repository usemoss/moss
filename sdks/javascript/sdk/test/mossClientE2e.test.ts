/**
 * E2E tests for MossClient against the real cloud API (/v1/manage).
 *
 * Tests the full async mutation lifecycle with thorough field-level assertions:
 *   createIndex → getIndex → addDocs → getDocs → deleteDocs → getJobStatus
 *   → loadIndex → query → deleteIndex
 *
 * Every response type is verified field-by-field to prevent regressions:
 *   - MutationResult:        jobId, indexName, docCount
 *   - JobStatusResponse:     jobId, status, progress, currentPhase, error,
 *                             createdAt, updatedAt, completedAt
 *   - JobProgress:           jobId, status, progress, currentPhase
 *   - IndexInfo:             name, docCount, model, createdAt, updatedAt
 *   - SearchResult:          docs[].id, docs[].text, docs[].score
 *
 * Prerequisites:
 *   - Set MOSS_TEST_PROJECT_ID and MOSS_TEST_PROJECT_KEY env vars
 *   - Ensure cloud API is accessible
 *
 * Run:
 *   npx vitest run test/mossClientE2e.test.ts
 */

import { describe, it, expect, beforeAll, afterAll } from "vitest";
import dotenv from "dotenv";
import { MossClient } from "../src/client/mossClient";
import type {
  MutationResult,
  JobProgress,
  JobStatusResponse,
  DocumentInfo,
} from "../src/models";
import {
  TEST_PROJECT_ID,
  TEST_PROJECT_KEY,
  TEST_DOCUMENTS,
  ADDITIONAL_TEST_DOCUMENTS,
  generateUniqueIndexName,
  HAS_REAL_CLOUD_CREDS,
} from "./constants";

dotenv.config();

const DIM = 4;
const V2_PREFIX = "test-v2-";

// Dummy embeddings — each doc gets a distinct unit-ish vector so queries are deterministic
function dummyEmbedding(seed: number): number[] {
  const v = new Array(DIM).fill(0);
  v[seed % DIM] = 1.0;
  return v;
}

const baseEmbeddings = TEST_DOCUMENTS.map((_, i) => dummyEmbedding(i));
const additionalEmbeddings = ADDITIONAL_TEST_DOCUMENTS.map((_, i) =>
  dummyEmbedding(i + TEST_DOCUMENTS.length),
);

describe.skipIf(!HAS_REAL_CLOUD_CREDS)("MossClient E2E (Cloud API)", () => {
  let client: MossClient;
  const createdIndexes: string[] = [];

  beforeAll(async () => {
    client = new MossClient(TEST_PROJECT_ID, TEST_PROJECT_KEY);
  });

  afterAll(async () => {
    try {
      const indexes = await client.listIndexes();
      for (const idx of indexes) {
        if (idx.name.startsWith(V2_PREFIX)) {
          try {
            await client.deleteIndex(idx.name);
          } catch {
            // ignore
          }
        }
      }
    } catch {
      // ignore
    }
  });

  describe("createIndex (custom embeddings)", () => {
    const indexName = generateUniqueIndexName(V2_PREFIX + "custom");
    let result: MutationResult;
    let progressUpdates: JobProgress[] = [];

    beforeAll(async () => {
      createdIndexes.push(indexName);
      const docs: DocumentInfo[] = TEST_DOCUMENTS.map((doc, i) => ({
        ...doc,
        embedding: baseEmbeddings[i],
      }));

      progressUpdates = [];
      result = await client.createIndex(indexName, docs, {
        modelId: "custom",
        onProgress: (p) => progressUpdates.push({ ...p }),
      });
    });

    // -- MutationResult field-by-field --

    it("result.jobId should be a non-empty string", () => {
      expect(typeof result.jobId).toBe("string");
      expect(result.jobId.length).toBeGreaterThan(0);
    });

    it("result.indexName should match the requested name", () => {
      expect(result.indexName).toBe(indexName);
    });

    it("result.docCount should match the number of docs provided", () => {
      expect(result.docCount).toBe(TEST_DOCUMENTS.length);
    });

    // -- JobProgress field-by-field --

    it("onProgress should include completed status", () => {
      const statuses = progressUpdates.map((p) => p.status);
      expect(statuses).toContain("completed");
    });

    it("onProgress callbacks should include the jobId", () => {
      for (const p of progressUpdates) {
        expect(p.jobId).toBe(result.jobId);
      }
    });

    it("onProgress completed update should have progress=100 and no currentPhase", () => {
      const completed = progressUpdates.find((p) => p.status === "completed");
      expect(completed).toBeDefined();
      expect(completed!.progress).toBe(100);
      expect(completed!.currentPhase).toBeFalsy();
    });

    // -- JobStatusResponse (getJobStatus) field-by-field --

    it("getJobStatus should return full response for the completed job", async () => {
      const status: JobStatusResponse = await client.getJobStatus(
        result.jobId,
      );

      expect(status.jobId).toBe(result.jobId);
      expect(status.status).toBe("completed");
      expect(status.progress).toBe(100);
      expect(status.currentPhase).toBeNull();
      expect(status.error).toBeFalsy();
      expect(typeof status.createdAt).toBe("string");
      expect(status.createdAt.length).toBeGreaterThan(0);
      expect(typeof status.updatedAt).toBe("string");
      expect(status.updatedAt.length).toBeGreaterThan(0);
      expect(typeof status.completedAt).toBe("string");
      expect(status.completedAt!.length).toBeGreaterThan(0);
    });

    // -- IndexInfo verification --

    it("getIndex should return matching index info", async () => {
      const info = await client.getIndex(indexName);
      expect(info.name).toBe(indexName);
      expect(info.docCount).toBe(TEST_DOCUMENTS.length);
      expect(info).toHaveProperty("model");
      expect(info).toHaveProperty("createdAt");
      expect(info).toHaveProperty("updatedAt");
    });

    it("listIndexes should include the created index", async () => {
      const indexes = await client.listIndexes();
      const names = indexes.map((idx) => idx.name);
      expect(names).toContain(indexName);
    });

    // -- Query verification --

    it("loadIndex + query should return scored results from our docs", async () => {
      await client.loadIndex(indexName);
      // Query with doc-1's embedding — should rank doc-1 first
      const queryEmbedding = baseEmbeddings[0];

      const results = await client.query(indexName, "", {
        embedding: queryEmbedding,
        topK: 3,
      });

      expect(results.docs.length).toBeGreaterThan(0);
      expect(results.docs.length).toBeLessThanOrEqual(3);

      for (const doc of results.docs) {
        expect(typeof doc.id).toBe("string");
        expect(typeof doc.text).toBe("string");
        expect(typeof doc.score).toBe("number");
        expect(doc.score).toBeGreaterThan(0);
        expect(doc.score).toBeLessThan(1.01);
      }

      const validIds = new Set(TEST_DOCUMENTS.map((d) => d.id));
      for (const doc of results.docs) {
        expect(validIds).toContain(doc.id);
      }
    });

    it("query results should be sorted by score descending", async () => {
      const queryEmbedding = baseEmbeddings[0];
      const results = await client.query(indexName, "", {
        embedding: queryEmbedding,
        topK: 5,
      });

      for (let i = 1; i < results.docs.length; i++) {
        expect(results.docs[i - 1]!.score).toBeGreaterThanOrEqual(
          results.docs[i]!.score,
        );
      }
    });
  });

  describe("createIndex (text-only, dimension=0)", () => {
    const indexName = generateUniqueIndexName(V2_PREFIX + "textonly");
    let result: MutationResult;
    let progressUpdates: JobProgress[] = [];

    beforeAll(async () => {
      createdIndexes.push(indexName);
      const docs: DocumentInfo[] = TEST_DOCUMENTS.map((doc) => ({
        id: doc.id,
        text: doc.text,
      }));

      progressUpdates = [];
      result = await client.createIndex(indexName, docs, {
        onProgress: (p) => progressUpdates.push({ ...p }),
      });
    });

    it("result should have valid jobId, indexName, docCount", () => {
      expect(result.jobId).toBeTruthy();
      expect(result.indexName).toBe(indexName);
      expect(result.docCount).toBe(TEST_DOCUMENTS.length);
    });

    it("onProgress should reach completed", () => {
      const statuses = progressUpdates.map((p) => p.status);
      expect(statuses).toContain("completed");
    });

    it("getIndex should show correct doc count", async () => {
      const info = await client.getIndex(indexName);
      expect(info.docCount).toBe(TEST_DOCUMENTS.length);
    });

    it("should be queryable with server-generated embeddings", async () => {
      await client.loadIndex(indexName);
      // Use a dummy vector matching the index dimension (server-generated)
      const results = await client.query(indexName, "artificial intelligence");

      expect(results.docs.length).toBeGreaterThan(0);
      expect(results.docs[0]!.score).toBeGreaterThan(0);
    });
  });

  describe("addDocs", () => {
    const indexName = generateUniqueIndexName(V2_PREFIX + "adddocs");
    let createResult: MutationResult;
    let addResult: MutationResult;
    let addProgress: JobProgress[] = [];

    beforeAll(async () => {
      createdIndexes.push(indexName);
      const docs: DocumentInfo[] = TEST_DOCUMENTS.map((doc, i) => ({
        ...doc,
        embedding: baseEmbeddings[i],
      }));
      createResult = await client.createIndex(indexName, docs, {
        modelId: "custom",
      });
    });

    // -- MutationResult from addDocs --

    it("should return MutationResult with valid jobId", async () => {
      addProgress = [];
      const docsWithEmbeddings: DocumentInfo[] = ADDITIONAL_TEST_DOCUMENTS.map(
        (doc, i) => ({
          ...doc,
          embedding: additionalEmbeddings[i],
        }),
      );
      addResult = await client.addDocs(
        indexName,
        docsWithEmbeddings,
        {
          onProgress: (p) => addProgress.push({ ...p }),
        },
      );

      expect(typeof addResult.jobId).toBe("string");
      expect(addResult.jobId.length).toBeGreaterThan(0);
    });

    it("addResult.indexName should match", () => {
      expect(addResult.indexName).toBe(indexName);
    });

    it("addResult.docCount should match the number of added docs", () => {
      expect(addResult.docCount).toBe(ADDITIONAL_TEST_DOCUMENTS.length);
    });

    // -- addDocs progress --

    it("onProgress should include completed status with jobId", () => {
      const completed = addProgress.find((p) => p.status === "completed");
      expect(completed).toBeDefined();
      expect(completed!.jobId).toBe(addResult.jobId);
      expect(completed!.progress).toBe(100);
    });

    // -- getJobStatus for addDocs --

    it("getJobStatus should show completed with timestamps", async () => {
      const status = await client.getJobStatus(addResult.jobId);

      expect(status.jobId).toBe(addResult.jobId);
      expect(status.status).toBe("completed");
      expect(status.progress).toBe(100);
      expect(status.currentPhase).toBeNull();
      expect(status.error).toBeFalsy();
      expect(status.createdAt).toBeTruthy();
      expect(status.updatedAt).toBeTruthy();
      expect(status.completedAt).toBeTruthy();
    });

    // -- Verify docs were actually added --

    it("getIndex should reflect total doc count", async () => {
      const info = await client.getIndex(indexName);
      expect(info.docCount).toBe(
        TEST_DOCUMENTS.length + ADDITIONAL_TEST_DOCUMENTS.length,
      );
    });

    it("getDocs should include the newly added documents", async () => {
      const docs = await client.getDocs(indexName);
      const docIds = docs.map((d) => d.id);

      for (const addedDoc of ADDITIONAL_TEST_DOCUMENTS) {
        expect(docIds).toContain(addedDoc.id);
      }
    });

    it("getDocs should return all original + added docs", async () => {
      const docs = await client.getDocs(indexName);
      expect(docs.length).toBe(
        TEST_DOCUMENTS.length + ADDITIONAL_TEST_DOCUMENTS.length,
      );

      for (const doc of docs) {
        expect(typeof doc.id).toBe("string");
        expect(typeof doc.text).toBe("string");
        expect(doc.id.length).toBeGreaterThan(0);
        expect(doc.text.length).toBeGreaterThan(0);
      }
    });

    it("getDocs with specific docIds should return only those docs", async () => {
      const targetIds = [
        ADDITIONAL_TEST_DOCUMENTS[0].id,
        TEST_DOCUMENTS[0].id,
      ];
      const docs = await client.getDocs(indexName, { docIds: targetIds });

      expect(docs.length).toBe(targetIds.length);
      const returnedIds = docs.map((d) => d.id);
      for (const id of targetIds) {
        expect(returnedIds).toContain(id);
      }
    });
  });

  describe("addDocs with upsert", () => {
    const indexName = generateUniqueIndexName(V2_PREFIX + "upsert");

    beforeAll(async () => {
      createdIndexes.push(indexName);
      const docs: DocumentInfo[] = TEST_DOCUMENTS.slice(0, 3).map(
        (doc, i) => ({
          ...doc,
          embedding: baseEmbeddings[i],
        }),
      );
      await client.createIndex(indexName, docs, { modelId: "custom" });
    });

    it("should upsert an existing document with updated text", async () => {
      const updatedDoc: DocumentInfo = {
        id: "doc-1",
        text: "UPDATED: Machine learning with modern deep learning techniques.",
        embedding: [0.6, 0.4, 0.0, 0.0],
      };

      const result = await client.addDocs(indexName, [updatedDoc], {
        upsert: true,
      });

      expect(result.jobId).toBeTruthy();
      expect(result.indexName).toBe(indexName);
      expect(result.docCount).toBe(1);
    });

    it("should reflect updated text in getDocs", async () => {
      const docs = await client.getDocs(indexName, { docIds: ["doc-1"] });
      expect(docs.length).toBe(1);
      expect(docs[0].text).toContain("UPDATED");
    });

    it("should maintain same doc count after upsert (no duplicates)", async () => {
      const info = await client.getIndex(indexName);
      expect(info.docCount).toBe(3);
    });
  });

  describe("deleteDocs", () => {
    const indexName = generateUniqueIndexName(V2_PREFIX + "deldocs");
    let deleteResult: MutationResult;
    let deleteProgress: JobProgress[] = [];

    beforeAll(async () => {
      createdIndexes.push(indexName);
      const docs: DocumentInfo[] = TEST_DOCUMENTS.map((doc, i) => ({
        ...doc,
        embedding: baseEmbeddings[i],
      }));
      await client.createIndex(indexName, docs, { modelId: "custom" });
    });

    // -- MutationResult from deleteDocs --

    it("should return MutationResult with valid jobId", async () => {
      deleteProgress = [];
      deleteResult = await client.deleteDocs(indexName, ["doc-3", "doc-4"], {
        onProgress: (p) => deleteProgress.push({ ...p }),
      });

      expect(typeof deleteResult.jobId).toBe("string");
      expect(deleteResult.jobId.length).toBeGreaterThan(0);
    });

    it("deleteResult.indexName should match", () => {
      expect(deleteResult.indexName).toBe(indexName);
    });

    it("deleteResult.docCount should match the number of deleted docIds", () => {
      expect(deleteResult.docCount).toBe(2);
    });

    // -- deleteDocs progress --

    it("onProgress should include completed status with jobId", () => {
      const completed = deleteProgress.find((p) => p.status === "completed");
      expect(completed).toBeDefined();
      expect(completed!.jobId).toBe(deleteResult.jobId);
      expect(completed!.progress).toBe(100);
    });

    // -- getJobStatus for deleteDocs --

    it("getJobStatus should show completed with all timestamp fields", async () => {
      const status = await client.getJobStatus(deleteResult.jobId);

      expect(status.jobId).toBe(deleteResult.jobId);
      expect(status.status).toBe("completed");
      expect(status.progress).toBe(100);
      expect(status.currentPhase).toBeNull();
      expect(status.error).toBeFalsy();
      expect(status.createdAt).toBeTruthy();
      expect(status.updatedAt).toBeTruthy();
      expect(status.completedAt).toBeTruthy();

      expect(new Date(status.createdAt).getTime()).not.toBeNaN();
      expect(new Date(status.updatedAt).getTime()).not.toBeNaN();
      expect(new Date(status.completedAt!).getTime()).not.toBeNaN();
    });

    // -- Verify docs were actually deleted --

    it("getIndex should reflect reduced doc count", async () => {
      const info = await client.getIndex(indexName);
      expect(info.docCount).toBe(TEST_DOCUMENTS.length - 2);
    });

    it("getDocs should not include deleted docs", async () => {
      const docs = await client.getDocs(indexName);
      const docIds = docs.map((d) => d.id);
      expect(docIds).not.toContain("doc-3");
      expect(docIds).not.toContain("doc-4");
    });

    it("getDocs should still include remaining docs", async () => {
      const docs = await client.getDocs(indexName);
      const docIds = docs.map((d) => d.id);
      expect(docIds).toContain("doc-1");
      expect(docIds).toContain("doc-2");
      expect(docIds).toContain("doc-5");
    });
  });

  describe("full lifecycle", () => {
    const indexName = generateUniqueIndexName(V2_PREFIX + "lifecycle");

    beforeAll(() => {
      createdIndexes.push(indexName);
    });

    it("should complete create → add → delete → query cycle with correct counts at every step", async () => {
      // 1. Create with 3 docs
      const initialDocs: DocumentInfo[] = TEST_DOCUMENTS.slice(0, 3).map(
        (doc, i) => ({
          ...doc,
          embedding: baseEmbeddings[i],
        }),
      );

      const createResult = await client.createIndex(indexName, initialDocs, {
        modelId: "custom",
      });
      expect(createResult.jobId).toBeTruthy();
      expect(createResult.docCount).toBe(3);

      let info = await client.getIndex(indexName);
      expect(info.docCount).toBe(3);

      // 2. Add 2 more docs
      const additionalDocs: DocumentInfo[] = ADDITIONAL_TEST_DOCUMENTS.map(
        (doc, i) => ({
          ...doc,
          embedding: additionalEmbeddings[i],
        }),
      );
      const addResult = await client.addDocs(
        indexName,
        additionalDocs,
      );
      expect(addResult.jobId).toBeTruthy();
      expect(addResult.jobId).not.toBe(createResult.jobId);

      info = await client.getIndex(indexName);
      expect(info.docCount).toBe(5);

      // 3. Delete 1 doc
      const deleteResult = await client.deleteDocs(indexName, ["doc-2"]);
      expect(deleteResult.jobId).toBeTruthy();
      expect(deleteResult.jobId).not.toBe(addResult.jobId);

      info = await client.getIndex(indexName);
      expect(info.docCount).toBe(4);

      // 4. Verify doc-2 is gone, others remain
      const docs = await client.getDocs(indexName);
      const docIds = docs.map((d) => d.id);
      expect(docIds).not.toContain("doc-2");
      expect(docIds).toContain("doc-1");
      expect(docIds).toContain("doc-3");
      expect(docIds).toContain("doc-6");
      expect(docIds).toContain("doc-7");

      // 5. Load and query
      await client.loadIndex(indexName);
      const results = await client.query(indexName, "", {
        embedding: baseEmbeddings[0],
        topK: 3,
      });

      expect(results.docs.length).toBeGreaterThan(0);
      for (const doc of results.docs) {
        expect(doc.score).toBeGreaterThan(0);
        expect(doc.id).not.toBe("doc-2");
      }

      // 6. All three jobs should be independently queryable via getJobStatus
      for (const jobId of [
        createResult.jobId,
        addResult.jobId,
        deleteResult.jobId,
      ]) {
        const status = await client.getJobStatus(jobId);
        expect(status.jobId).toBe(jobId);
        expect(status.status).toBe("completed");
        expect(status.progress).toBe(100);
      }
    });
  });

  describe("deleteIndex", () => {
    const indexName = generateUniqueIndexName(V2_PREFIX + "delidx");

    beforeAll(async () => {
      const docs: DocumentInfo[] = TEST_DOCUMENTS.slice(0, 2).map(
        (doc, i) => ({
          ...doc,
          embedding: baseEmbeddings[i],
        }),
      );
      await client.createIndex(indexName, docs, { modelId: "custom" });
    });

    it("should delete the index and return true", async () => {
      const result = await client.deleteIndex(indexName);
      expect(result).toBe(true);
    });

    it("should no longer appear in listIndexes", async () => {
      const indexes = await client.listIndexes();
      const names = indexes.map((idx) => idx.name);
      expect(names).not.toContain(indexName);
    });

    it("getIndex should throw for the deleted index", async () => {
      await expect(client.getIndex(indexName)).rejects.toThrow();
    });
  });

  describe("error handling", () => {
    it("should throw for addDocs on non-existent index", async () => {
      await expect(
        client.addDocs("non-existent-v2-idx", [{ id: "x", text: "t" }]),
      ).rejects.toThrow();
    });

    it("should throw for deleteDocs on non-existent index", async () => {
      await expect(
        client.deleteDocs("non-existent-v2-idx", ["x"]),
      ).rejects.toThrow();
    });

    it("should throw for getIndex on non-existent index", async () => {
      await expect(
        client.getIndex("non-existent-v2-idx"),
      ).rejects.toThrow();
    });

    it("should throw for getDocs on non-existent index", async () => {
      await expect(
        client.getDocs("non-existent-v2-idx"),
      ).rejects.toThrow();
    });

    it("should throw for empty docs in createIndex (client-side)", async () => {
      await expect(client.createIndex("x", [])).rejects.toThrow(
        "at least one document",
      );
    });

    it("should throw for empty docs in addDocs (client-side)", async () => {
      await expect(client.addDocs("x", [])).rejects.toThrow(
        "at least one document",
      );
    });

    it("should throw for empty docIds in deleteDocs (client-side)", async () => {
      await expect(client.deleteDocs("x", [])).rejects.toThrow(
        "at least one document ID",
      );
    });

    it("should throw for cloud query on non-existent index", async () => {
      await expect(
        client.query("non-existent-v2-idx", "test"),
      ).rejects.toThrow();
    });
  });
});

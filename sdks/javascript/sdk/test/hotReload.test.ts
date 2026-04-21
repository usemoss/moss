import { describe, it, expect, beforeAll, afterAll } from "vitest";
import dotenv from "dotenv";
import {
  MossClient,
  DocumentInfo,
  MutationResult,
} from "../src/index";
import {
  TEST_PROJECT_ID,
  TEST_PROJECT_KEY,
  TEST_MODEL_ID,
  TEST_DOCUMENTS,
  generateUniqueIndexName,
  HAS_REAL_CLOUD_CREDS,
} from "./constants";

dotenv.config();

describe.skipIf(!HAS_REAL_CLOUD_CREDS)("Hot Reload E2E Tests", () => {
  async function createTestIndex(
    client: MossClient,
    indexName: string,
  ): Promise<MutationResult> {
    try {
      await client.deleteIndex(indexName);
    } catch {
      // Index may not exist, ignore
    }

    const docs: DocumentInfo[] = TEST_DOCUMENTS.map((doc) => ({
      id: doc.id,
      text: doc.text,
    }));

    return client.createIndex(indexName, docs, { modelId: TEST_MODEL_ID });
  }

  async function cleanupTestIndex(
    client: MossClient,
    indexName: string,
  ): Promise<void> {
    try {
      await client.deleteIndex(indexName);
    } catch (error) {
      console.warn(`Failed to clean up index ${indexName}:`, error);
    }
  }

  describe("Load Index with Auto-Refresh", () => {
    let client: MossClient;
    let indexName: string;
    let indexCreated: MutationResult | null = null;

    beforeAll(async () => {
      client = new MossClient(TEST_PROJECT_ID, TEST_PROJECT_KEY);
      indexName = generateUniqueIndexName("test-auto-refresh");
      indexCreated = await createTestIndex(client, indexName);
    });

    afterAll(async () => {
      if (indexCreated) {
        await cleanupTestIndex(client, indexName);
      }
    });

    it("should load index without auto-refresh by default", async () => {
      const loadedName = await client.loadIndex(indexName);
      expect(loadedName).toBe(indexName);
    });

    it("should load index with auto-refresh enabled", async () => {
      const loadedName = await client.loadIndex(indexName, {
        autoRefresh: true,
        pollingIntervalInSeconds: 600,
      });
      expect(loadedName).toBe(indexName);
    });

    it("should accept custom polling interval", async () => {
      // Load with a custom polling interval (5 minutes)
      const loadedName = await client.loadIndex(indexName, {
        autoRefresh: true,
        pollingIntervalInSeconds: 300,
      });
      expect(loadedName).toBe(indexName);

      // Clean up
      await client.loadIndex(indexName);
    });

    it("should allow reloading an already loaded index", async () => {
      // First load
      await client.loadIndex(indexName);

      // Second load should not throw (reloads the index)
      const loadedName = await client.loadIndex(indexName);
      expect(loadedName).toBe(indexName);
    });

    it("should stop auto-refresh when reloading without the option", async () => {
      // Load with auto-refresh
      await client.loadIndex(indexName, {
        autoRefresh: true,
        pollingIntervalInSeconds: 600,
      });

      // Reload without auto-refresh (stops polling)
      const loadedName = await client.loadIndex(indexName);
      expect(loadedName).toBe(indexName);
    });

    it("should replace auto-refresh settings when reloading with different interval", async () => {
      // Load with 10 minute interval
      await client.loadIndex(indexName, {
        autoRefresh: true,
        pollingIntervalInSeconds: 600,
      });

      // Reload with 5 minute interval (should replace)
      const loadedName = await client.loadIndex(indexName, {
        autoRefresh: true,
        pollingIntervalInSeconds: 300,
      });
      expect(loadedName).toBe(indexName);

      // Clean up
      await client.loadIndex(indexName);
    });

    it("should be able to query after loading with auto-refresh", async () => {
      await client.loadIndex(indexName, {
        autoRefresh: true,
        pollingIntervalInSeconds: 600,
      });

      const results = await client.query(indexName, "machine learning", {
        topK: 3,
      });

      expect(results).toHaveProperty("docs");
      expect(Array.isArray(results.docs)).toBe(true);
      expect(results.docs.length).toBeGreaterThan(0);

      // Clean up by reloading without auto-refresh
      await client.loadIndex(indexName);
    });
  });

  describe("Query Behavior", () => {
    let client: MossClient;
    let indexName: string;
    let indexCreated: MutationResult | null = null;

    beforeAll(async () => {
      client = new MossClient(TEST_PROJECT_ID, TEST_PROJECT_KEY);
      indexName = generateUniqueIndexName("test-query-behavior");
      indexCreated = await createTestIndex(client, indexName);
    });

    afterAll(async () => {
      if (indexCreated) {
        await cleanupTestIndex(client, indexName);
      }
    });

    it("should query cloud when index is not loaded locally", async () => {
      // Query without loading - should fall back to cloud
      const results = await client.query(indexName, "machine learning", {
        topK: 3,
      });

      expect(results).toHaveProperty("docs");
      expect(Array.isArray(results.docs)).toBe(true);
      expect(results.docs.length).toBeGreaterThan(0);
    });

    it("should query locally after loading index", async () => {
      // Load index locally
      await client.loadIndex(indexName);

      // Query should use local index (faster)
      const results = await client.query(indexName, "neural networks", {
        topK: 3,
      });

      expect(results).toHaveProperty("docs");
      expect(Array.isArray(results.docs)).toBe(true);
      expect(results.docs.length).toBeGreaterThan(0);
    });
  });

  describe("Multiple Indexes", () => {
    let client: MossClient;
    let indexName1: string;
    let indexName2: string;
    let index1Created: MutationResult | null = null;
    let index2Created: MutationResult | null = null;

    beforeAll(async () => {
      client = new MossClient(TEST_PROJECT_ID, TEST_PROJECT_KEY);
      indexName1 = generateUniqueIndexName("test-multi-1");
      indexName2 = generateUniqueIndexName("test-multi-2");
      index1Created = await createTestIndex(client, indexName1);
      index2Created = await createTestIndex(client, indexName2);
    });

    afterAll(async () => {
      if (index1Created) {
        await cleanupTestIndex(client, indexName1);
      }
      if (index2Created) {
        await cleanupTestIndex(client, indexName2);
      }
    });

    it("should handle multiple indexes with different auto-refresh settings", async () => {
      // Load first index with auto-refresh
      const loaded1 = await client.loadIndex(indexName1, {
        autoRefresh: true,
        pollingIntervalInSeconds: 600,
      });
      expect(loaded1).toBe(indexName1);

      // Load second index without auto-refresh
      const loaded2 = await client.loadIndex(indexName2);
      expect(loaded2).toBe(indexName2);

      // Both should be queryable
      const results1 = await client.query(indexName1, "machine learning", {
        topK: 2,
      });
      expect(results1.docs.length).toBeGreaterThan(0);

      const results2 = await client.query(indexName2, "neural networks", {
        topK: 2,
      });
      expect(results2.docs.length).toBeGreaterThan(0);

      // Clean up
      await client.loadIndex(indexName1);
    });
  });

  describe("Error Handling", () => {
    let client: MossClient;
    const nonExistentIndexName = "non-existent-index-for-test";

    beforeAll(() => {
      client = new MossClient(TEST_PROJECT_ID, TEST_PROJECT_KEY);
    });

    it("should fail to load a non-existent index", async () => {
      await expect(client.loadIndex(nonExistentIndexName)).rejects.toThrow();
    });

    it("should fail to query a non-existent index", async () => {
      await expect(
        client.query(nonExistentIndexName, "test query"),
      ).rejects.toThrow();
    });
  });
});

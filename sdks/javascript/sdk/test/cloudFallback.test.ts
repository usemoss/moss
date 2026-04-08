import { describe, it, expect, beforeAll, afterAll } from "vitest";
import dotenv from "dotenv";
import { MossClient, QueryResultDocumentInfo, MutationResult } from "../src/index";
import {
  TEST_PROJECT_ID,
  TEST_PROJECT_KEY,
  TEST_MODEL_ID,
  TEST_DOCUMENTS,
  generateUniqueIndexName,
  HAS_REAL_CLOUD_CREDS,
} from "./constants";

dotenv.config();

const CLOUD_FALLBACK_INDEX_NAME = generateUniqueIndexName("test-cloud-fallback");

describe.skipIf(!HAS_REAL_CLOUD_CREDS)("Cloud Fallback Query Operations", () => {
  let client: MossClient;
  let indexCreated: MutationResult | null = null;

  beforeAll(async () => {
    client = new MossClient(TEST_PROJECT_ID, TEST_PROJECT_KEY);

    try {
      await client.deleteIndex(CLOUD_FALLBACK_INDEX_NAME);
    } catch (error) {
      console.warn(
        `Failed to clean up existing index ${CLOUD_FALLBACK_INDEX_NAME}:`,
        error,
      );
      // Index might not exist, that's fine
    }

    indexCreated = await client.createIndex(
      CLOUD_FALLBACK_INDEX_NAME,
      TEST_DOCUMENTS,
      { modelId: TEST_MODEL_ID },
    );
  });

  afterAll(async () => {
    if (indexCreated) {
      try {
        await client.deleteIndex(CLOUD_FALLBACK_INDEX_NAME);
      } catch (error) {
        console.warn(
          `Failed to clean up index ${CLOUD_FALLBACK_INDEX_NAME}:`,
          error,
        );
      }
    }
  });

  it("should query via cloud when index is not loaded locally", async () => {
    // Query WITHOUT calling loadIndex() first - should fall back to cloud API
    const results = await client.query(
      CLOUD_FALLBACK_INDEX_NAME,
      "artificial intelligence",
      { topK: 5 },
    );

    // Verify response structure
    expect(results).toHaveProperty("docs");
    expect(Array.isArray(results.docs)).toBe(true);
    expect(results.docs.length).toBeGreaterThan(0);
    expect(results.docs.length).toBeLessThanOrEqual(5);

    // Verify each doc has required fields
    results.docs.forEach((doc: QueryResultDocumentInfo) => {
      expect(doc).toHaveProperty("id");
      expect(doc).toHaveProperty("text");
      expect(doc).toHaveProperty("score");
      expect(typeof doc.id).toBe("string");
      expect(typeof doc.text).toBe("string");
      expect(typeof doc.score).toBe("number");
      // Scores should be in range (0, 1]
      expect(doc.score).toBeGreaterThan(0);
      expect(doc.score).toBeLessThanOrEqual(1);
    });

    // Verify scores are in descending order (sorted by relevance)
    for (let i = 1; i < results.docs.length; i++) {
      expect(results.docs[i - 1].score).toBeGreaterThanOrEqual(
        results.docs[i].score,
      );
    }
  });

  it("should respect topK parameter in cloud fallback", async () => {
    const topK = 2;
    const results = await client.query(
      CLOUD_FALLBACK_INDEX_NAME,
      "machine learning",
      { topK },
    );

    expect(results.docs.length).toBeLessThanOrEqual(topK);
  });

  it("should return results consistent with local query after loading", async () => {
    // Step 1: Query via cloud (before loadIndex)
    const cloudResults = await client.query(
      CLOUD_FALLBACK_INDEX_NAME,
      "neural networks deep learning",
      { topK: 5 },
    );

    // Step 2: Load the index locally
    await client.loadIndex(CLOUD_FALLBACK_INDEX_NAME);

    // Step 3: Query via local (after loadIndex)
    const localResults = await client.query(
      CLOUD_FALLBACK_INDEX_NAME,
      "neural networks deep learning",
      { topK: 5 },
    );

    // Both should return results
    expect(cloudResults.docs.length).toBeGreaterThan(0);
    expect(localResults.docs.length).toBeGreaterThan(0);

    // Top result (first doc ID) should match
    expect(cloudResults.docs[0].id).toBe(localResults.docs[0].id);

    // Significant overlap in result IDs (at least N-1 overlap)
    const cloudIds = cloudResults.docs.map((doc) => doc.id);
    const localIds = localResults.docs.map((doc) => doc.id);
    const overlap = cloudIds.filter((id) => localIds.includes(id));
    const minOverlap = Math.min(cloudIds.length, localIds.length) - 1;
    expect(overlap.length).toBeGreaterThanOrEqual(minOverlap);
  });
});

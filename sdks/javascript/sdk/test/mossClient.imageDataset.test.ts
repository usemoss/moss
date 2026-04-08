import { describe, it, expect, beforeAll, afterAll } from "vitest";
import dotenv from "dotenv";
import { readFileSync } from "node:fs";
import { MossClient, DocumentInfo } from "../src/index";
import {
  TEST_PROJECT_ID,
  TEST_PROJECT_KEY,
  TEST_MODEL_ID,
  generateUniqueIndexName,
  HAS_REAL_CLOUD_CREDS,
} from "./constants";

dotenv.config();

// Generate unique index name for this test run
const TEST_IMAGE_INDEX_NAME = generateUniqueIndexName("test-image-dataset");

const IMAGE_DATASET_DOCUMENTS = JSON.parse(
  readFileSync(new URL("./image-data-1k.json", import.meta.url), "utf-8"),
) as DocumentInfo[];

describe.skipIf(!HAS_REAL_CLOUD_CREDS)("MossClient Large Dataset Ingestion", () => {
  let client: MossClient;

  beforeAll(async () => {
    client = new MossClient(TEST_PROJECT_ID, TEST_PROJECT_KEY);

    try {
      await client.deleteIndex(TEST_IMAGE_INDEX_NAME);
    } catch (error) {
      console.warn(
        `Failed to clean up existing index ${TEST_IMAGE_INDEX_NAME}:`,
        error,
      );
    }
  });

  afterAll(async () => {
    try {
      await client.deleteIndex(TEST_IMAGE_INDEX_NAME);
    } catch (error) {
      console.warn(`Failed to clean up index ${TEST_IMAGE_INDEX_NAME}:`, error);
    }
  });

  it("should create an index with image descriptions", async () => {
    console.log(`Creating index ${TEST_IMAGE_INDEX_NAME} with ${IMAGE_DATASET_DOCUMENTS.length} documents...`);
    const result = await client.createIndex(
      TEST_IMAGE_INDEX_NAME,
      IMAGE_DATASET_DOCUMENTS,
      { modelId: TEST_MODEL_ID },
    );

    expect(result).toHaveProperty("jobId");
    expect(result).toHaveProperty("indexName", TEST_IMAGE_INDEX_NAME);
    expect(result).toHaveProperty("docCount", IMAGE_DATASET_DOCUMENTS.length);

    const indexInfo = await client.getIndex(TEST_IMAGE_INDEX_NAME);
    expect(indexInfo.docCount).toBe(IMAGE_DATASET_DOCUMENTS.length);
  });
});

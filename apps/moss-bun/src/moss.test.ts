/**
 * Moss Bun Tests
 *
 * Tests for Moss SDK integration with Bun
 */

import { describe, it, expect, beforeAll, afterAll } from "bun:test";
import { MossClient } from "@moss-dev/moss";
import { config } from "dotenv";

config();

const MOSS_PROJECT_ID = process.env.MOSS_PROJECT_ID || "";
const MOSS_PROJECT_KEY = process.env.MOSS_PROJECT_KEY || "";

// Skip tests if credentials are not set
const testIndexName = `moss-bun-test-${Date.now()}`;
const hasMossCredentials = Boolean(MOSS_PROJECT_ID && MOSS_PROJECT_KEY);
let client: MossClient;
(hasMossCredentials ? describe : describe.skip)("Moss Bun Integration", () => {
  beforeAll(() => {
    client = new MossClient(MOSS_PROJECT_ID, MOSS_PROJECT_KEY);
  });

  describe("Index Operations", () => {
    it("should create an index with documents", async () => {
      const documents = [
        { id: "1", text: "Moss is a semantic search runtime" },
        { id: "2", text: "Bun is a JavaScript runtime" },
        { id: "3", text: "TypeScript adds static typing" },
      ];

      const startTime = Date.now();
      await client.createIndex(testIndexName, documents);
      const elapsed = Date.now() - startTime;

      console.log(`   Created index in ${elapsed}ms`);
      expect(true).toBe(true);
    }, { timeout: 15000 }); // 15 second timeout for API call

    it("should load an index", async () => {
      const startTime = Date.now();
      await client.loadIndex(testIndexName);
      const elapsed = Date.now() - startTime;

      console.log(`   Loaded index in ${elapsed}ms`);
      expect(true).toBe(true);
    }, { timeout: 10000 }); // 10 second timeout
  });

  describe("Search Operations", () => {
    it("should perform a semantic search", async () => {
      const results = await client.query(testIndexName, "what is moss?", { topK: 3 });

      expect(results.docs).toBeArray();
      expect(results.timeTakenInMs).toBeGreaterThanOrEqual(0); // Can be 0ms (< 1ms)

      if (results.docs.length > 0) {
        expect(results.docs[0].score).toBeLessThanOrEqual(1);
        expect(results.docs[0].score).toBeGreaterThanOrEqual(0);
      }
    }, { timeout: 10000 });

    it("should handle batch queries", async () => {
      const queries = ["moss", "bun", "typescript"];
      const results = await Promise.all(
        queries.map((q) => client.query(testIndexName, q, { topK: 2 }))
      );

      expect(results).toHaveLength(3);
      results.forEach((result) => {
        expect(result.docs).toBeArray();
      });
    }, { timeout: 15000 });

    it("should respect topK parameter", async () => {
      const topK = 2;
      const results = await client.query(testIndexName, "search", { topK });

      expect(results.docs.length).toBeLessThanOrEqual(topK);
    }, { timeout: 10000 });
  });

  describe("Document Operations", () => {
    it("should add documents", async () => {
      const newDocs = [{ id: "4", text: "New document about Moss" }];

      await client.addDocs(testIndexName, newDocs, { upsert: true });
      expect(true).toBe(true);
    }, { timeout: 10000 });

    it("should get documents by ID", async () => {
      const docs = await client.getDocs(testIndexName, { docIds: ["1"] });

      expect(docs).toBeArray();
      if (docs.length > 0) {
        expect(docs[0].id).toBe("1");
        expect(docs[0].text).toContain("Moss");
      }
    }, { timeout: 10000 });
  });

  describe("Performance", () => {
    it("should complete queries in reasonable time", async () => {
      const start = Date.now();
      const results = await client.query(testIndexName, "moss", { topK: 5 });
      const elapsed = Date.now() - start;

      console.log(`   Query completed in ${elapsed}ms (Moss: ${results.timeTakenInMs}ms)`);

      // Bun + Moss should be quite fast
      expect(elapsed).toBeLessThan(15000);
      expect(results.timeTakenInMs).toBeLessThan(10000);
    }, { timeout: 15000 });
  });

  afterAll(async () => {
    try {
      // Cleanup: delete test index
      await client.deleteIndex(testIndexName);
    } catch (error) {
      // Ignore cleanup errors
    }
  });
});

describe("Bun Runtime Features", () => {
  it("should have access to Bun APIs", () => {
    expect(Bun).toBeDefined();
    expect(Bun.env).toBeDefined();
  });

  it("should measure memory usage", () => {
    const mem = process.memoryUsage();

    expect(mem.rss).toBeGreaterThan(0);
    expect(mem.heapUsed).toBeGreaterThan(0);
    expect(mem.heapTotal).toBeGreaterThan(0);
  });

  it("should measure uptime", () => {
    expect(process.uptime()).toBeGreaterThan(0);
  });
});

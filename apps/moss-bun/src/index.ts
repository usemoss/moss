/**
 * Moss Bun Server
 *
 * Production-ready REST API for Moss semantic search
 * Built with Bun + Elysia
 */

import { Elysia } from "elysia";
import { MossClient } from "@moss-dev/moss";
import { config } from "dotenv";

// Load environment variables
config();

interface SearchRequest {
  query: string;
  topK?: number;
  indexName?: string;
}

interface SearchResponse {
  success: boolean;
  query?: string;
  results?: Array<{
    id: string;
    text: string;
    score: number;
    metadata?: Record<string, unknown>;
  }>;
  timeTakenMs?: number;
  error?: string;
}

interface InitializeRequest {
  indexName: string;
  documents: Array<{
    id: string;
    text: string;
    metadata?: Record<string, unknown>;
  }>;
}

// Environment variables
const MOSS_PROJECT_ID = process.env.MOSS_PROJECT_ID || "";
const MOSS_PROJECT_KEY = process.env.MOSS_PROJECT_KEY || "";
const PORT = parseInt(process.env.PORT || "3000");
const DEFAULT_INDEX = process.env.DEFAULT_INDEX || "default";

if (!MOSS_PROJECT_ID || !MOSS_PROJECT_KEY) {
  console.error("❌ Error: MOSS_PROJECT_ID and MOSS_PROJECT_KEY are required");
  console.error("Set them in .env file or environment variables");
  process.exit(1);
}

// Initialize Moss client
const mossClient = new MossClient(MOSS_PROJECT_ID, MOSS_PROJECT_KEY);

// Track loaded indexes
const loadedIndexes = new Set<string>();

// Track in-flight loads to prevent race conditions
const loadingIndexes = new Map<string, Promise<boolean>>();

/**
 * Load an index if not already loaded
 * Prevents race conditions by deduplicating concurrent loads
 */
async function ensureIndexLoaded(indexName: string): Promise<boolean> {
  // Return immediately if already loaded
  if (loadedIndexes.has(indexName)) {
    return true;
  }

  // Return existing in-flight promise if load is already in progress
  if (loadingIndexes.has(indexName)) {
    return loadingIndexes.get(indexName)!;
  }

  // Create new load promise
  let loadPromise: Promise<boolean>;
  loadPromise = (async () => {
    try {
      await mossClient.loadIndex(indexName);
      loadedIndexes.add(indexName);
      return true;
    } catch (error) {
      console.error(`Failed to load index "${indexName}":`, error);
      return false;
    } finally {
      // Only delete if this is still our entry (another operation may have overwritten it)
      if (loadingIndexes.get(indexName) === loadPromise) {
        loadingIndexes.delete(indexName);
      }
    }
  })();

  // Track in-flight load
  loadingIndexes.set(indexName, loadPromise);

  return loadPromise;
}

/**
 * Create Elysia server
 */
const app = new Elysia()
  // ============================================================================
  // HEALTH & STATUS
  // ============================================================================
  .get("/health", () => {
    return {
      status: "ok",
      service: "moss-bun",
      timestamp: new Date().toISOString(),
      loadedIndexes: Array.from(loadedIndexes),
    };
  })

  .get("/status", () => {
    return {
      service: "moss-bun",
      version: "1.0.0",
      runtime: "bun",
      uptime: process.uptime(),
      memory: process.memoryUsage(),
      indexes: Array.from(loadedIndexes),
    };
  })

 
  .post("/api/initialize", async ({ body }: any) => {
    try {
      const { indexName, documents } = body;

      if (!indexName || !documents || !Array.isArray(documents)) {
        return {
          success: false,
          error: "Invalid request: indexName and documents array are required",
        };
      }

      if (documents.length === 0) {
        return {
          success: false,
          error: "Documents array cannot be empty",
        };
      }

      console.log(
        `📝 Creating index "${indexName}" with ${documents.length} documents...`
      );

      // Register this initialize operation in loadingIndexes so that concurrent
      // ensureIndexLoaded calls will wait on it instead of starting their own load
      const initPromise: Promise<boolean> = (async () => {
        try {
          // Invalidate cache first — createIndex changes server state, so the
          // previously-loaded in-memory index is stale regardless of whether
          // the subsequent loadIndex succeeds.
          loadedIndexes.delete(indexName);
          await mossClient.createIndex(indexName, documents);

          // Load index
          await mossClient.loadIndex(indexName);
          loadedIndexes.add(indexName);
          return true;
        } catch (error) {
          console.error(`Failed to initialize index "${indexName}":`, error);
          return false;
        } finally {
          // Only delete if this is still our entry (another operation may have overwritten it)
          if (loadingIndexes.get(indexName) === initPromise) {
            loadingIndexes.delete(indexName);
          }
        }
      })();

      // Register the in-flight initialize operation
      loadingIndexes.set(indexName, initPromise);

      // Wait for it to complete
      const success = await initPromise;

      if (!success) {
        return {
          success: false,
          error: `Failed to create and load index "${indexName}"`,
        };
      }

      console.log(`✓ Index "${indexName}" created and loaded`);

      return {
        success: true,
        message: `Index "${indexName}" created with ${documents.length} documents`,
        indexName,
        documentCount: documents.length,
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      console.error("Initialize error:", errorMsg);
      return { success: false, error: errorMsg };
    }
  })

  .post("/api/load/:indexName", async ({ params }: { params: { indexName: string } }) => {
    try {
      const { indexName } = params;

      if (loadedIndexes.has(indexName)) {
        return { success: true, message: `Index "${indexName}" already loaded` };
      }

      console.log(`🔄 Loading index "${indexName}"...`);
      const isLoaded = await ensureIndexLoaded(indexName);
      if (!isLoaded) {
        return { success: false, error: `Index "${indexName}" could not be loaded` };
      }

      return { success: true, message: `Index "${indexName}" loaded successfully` };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return { success: false, error: errorMsg };
    }
  })

  .get("/api/indexes", () => {
    return {
      success: true,
      indexes: Array.from(loadedIndexes),
      count: loadedIndexes.size,
    };
  })

  .delete("/api/index/:indexName", async ({ params }: { params: { indexName: string } }) => {
    try {
      const { indexName } = params;

      await mossClient.deleteIndex(indexName);
      loadedIndexes.delete(indexName);

      return { success: true, message: `Index "${indexName}" deleted` };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return { success: false, error: errorMsg };
    }
  })

  // ============================================================================
  // SEARCH
  // ============================================================================
  .post("/api/search", async ({ body }: { body: SearchRequest }): Promise<SearchResponse> => {
    try {
      const { query, topK = 5, indexName = DEFAULT_INDEX } = body;

      if (!query) {
        return { success: false, error: "Query is required" };
      }

      // Ensure index is loaded
      const isLoaded = await ensureIndexLoaded(indexName);
      if (!isLoaded) {
        return {
          success: false,
          error: `Index "${indexName}" not found or could not be loaded`,
        };
      }

      console.log(`🔍 Searching "${indexName}" for: "${query}"`);

      const startTime = Date.now();
      const results = await mossClient.query(indexName, query, { topK });
      const elapsedTime = Date.now() - startTime;

      console.log(
        `✓ Found ${results.docs.length} results in ${results.timeTakenInMs}ms (Bun: ${elapsedTime}ms)`
      );

      return {
        success: true,
        query,
        results: results.docs.map((doc) => ({
          id: doc.id,
          text: doc.text,
          score: doc.score,
          metadata: doc.metadata,
        })),
        timeTakenMs: results.timeTakenInMs,
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      console.error("Search error:", errorMsg);
      return { success: false, error: errorMsg };
    }
  })

  // Batch search
  .post(
    "/api/search-batch",
    async ({
      body,
    }: {
      body: { queries: string[]; topK?: number; indexName?: string };
    }) => {
      try {
        const { queries, topK = 5, indexName = DEFAULT_INDEX } = body;

        if (!Array.isArray(queries) || queries.length === 0) {
          return { success: false, error: "Queries array is required" };
        }

        const isLoaded = await ensureIndexLoaded(indexName);
        if (!isLoaded) {
          return { success: false, error: `Index "${indexName}" not found` };
        }

        console.log(`🔍 Batch search: ${queries.length} queries on "${indexName}"`);

        const results = await Promise.all(
          queries.map(async (query) => {
            const queryResults = await mossClient.query(indexName, query, { topK });
            return {
              query,
              results: queryResults.docs.map((doc) => ({
                id: doc.id,
                text: doc.text,
                score: doc.score,
              })),
              timeTakenMs: queryResults.timeTakenInMs,
            };
          })
        );

        return {
          success: true,
          batchSize: queries.length,
          results,
        };
      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : String(error);
        return { success: false, error: errorMsg };
      }
    }
  )

  // ============================================================================
  // DOCUMENT OPERATIONS
  // ============================================================================
  .post(
    "/api/docs/add",
    async ({
      body,
    }: {
      body: { indexName: string; documents: Array<{ id: string; text: string }> };
    }) => {
      try {
        const { indexName, documents } = body;

        if (!indexName || !Array.isArray(documents) || documents.length === 0) {
          return { success: false, error: "indexName and documents are required" };
        }

        const isLoaded = await ensureIndexLoaded(indexName);
        if (!isLoaded) {
          return { success: false, error: `Index "${indexName}" not found` };
        }

        console.log(`➕ Adding ${documents.length} documents to "${indexName}"`);

        await mossClient.addDocs(indexName, documents, { upsert: true });

        // Reload index to ensure queries return updated data
        try {
          await mossClient.loadIndex(indexName);
        } catch (reloadError) {
          // Invalidate cache so subsequent requests will retry the reload
          loadedIndexes.delete(indexName);
          console.error(`Failed to reload index "${indexName}" after adding documents:`, reloadError);
          throw reloadError;
        }

        return {
          success: true,
          message: `Added ${documents.length} documents to "${indexName}"`,
          count: documents.length,
        };
      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : String(error);
        return { success: false, error: errorMsg };
      }
    }
  )

  .delete("/api/docs/delete", async ({ body }: { body: { indexName: string; docIds: string[] } }) => {
    try {
      const { indexName, docIds } = body;

      if (!indexName || !Array.isArray(docIds) || docIds.length === 0) {
        return { success: false, error: "indexName and docIds array are required" };
      }

      const isLoaded = await ensureIndexLoaded(indexName);
      if (!isLoaded) {
        return { success: false, error: `Index "${indexName}" not found` };
      }

      await mossClient.deleteDocs(indexName, docIds);

      // Reload index to ensure queries return updated data
      try {
        await mossClient.loadIndex(indexName);
      } catch (reloadError) {
        // Invalidate cache so subsequent requests will retry the reload
        loadedIndexes.delete(indexName);
        console.error(`Failed to reload index "${indexName}" after deleting documents:`, reloadError);
        throw reloadError;
      }

      return {
        success: true,
        message: `Deleted ${docIds.length} documents from "${indexName}"`,
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return { success: false, error: errorMsg };
    }
  })

  .get(
    "/api/docs/:indexName/:docId",
    async ({ params }: { params: { indexName: string; docId: string } }) => {
      try {
        const { indexName, docId } = params;

        const isLoaded = await ensureIndexLoaded(indexName);
        if (!isLoaded) {
          return { success: false, error: `Index "${indexName}" not found` };
        }

        const docs = await mossClient.getDocs(indexName, { docIds: [docId] });

        if (docs.length === 0) {
          return { success: false, error: `Document "${docId}" not found` };
        }

        return { success: true, doc: docs[0] };
      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : String(error);
        return { success: false, error: errorMsg };
      }
    }
  )

  // ============================================================================
  // INFO
  // ============================================================================
  .get("/api/index/:indexName", async ({ params }: { params: { indexName: string } }) => {
    try {
      const { indexName } = params;

      const indexInfo = await mossClient.getIndex(indexName);

      return {
        success: true,
        index: indexInfo,
        isLoaded: loadedIndexes.has(indexName),
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return { success: false, error: errorMsg };
    }
  })

  .listen(PORT);

console.log(`🌿 Moss Bun Server listening on http://localhost:${PORT}`);

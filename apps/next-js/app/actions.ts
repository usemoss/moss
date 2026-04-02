'use server'

import { MossClient } from "@inferedge/moss";

// Module-level singleton — survives across requests in the same server process
let client: MossClient | null = null;
let indexLoadPromise: Promise<unknown> | null = null;

function getClient() {
  const projectId = process.env.MOSS_PROJECT_ID;
  const projectKey = process.env.MOSS_PROJECT_KEY;
  if (!projectId || !projectKey) {
    throw new Error("Missing MOSS_PROJECT_ID or MOSS_PROJECT_KEY.");
  }
  if (!client) {
    client = new MossClient(projectId, projectKey);
  }
  return client;
}

export type DocInput = {
  id: string;
  text: string;
  metadata?: Record<string, string>;
};

export async function deleteIndex(indexName: string) {
  try {
    await getClient().deleteIndex(indexName);
    indexLoadPromise = null;
    return { success: true as const };
  } catch (error) {
    // Silently ignore if index doesn't exist (404 errors)
    if (error instanceof Error && error.message.includes('404')) {
      return { success: true as const };
    }
    return { success: false as const, error: error instanceof Error ? error.message : 'Unknown error' };
  }
}

export async function createMossIndex(indexName: string, docs: DocInput[]) {
  const start = Date.now();
  try {
    // Delete existing index first to avoid conflicts
    await deleteIndex(indexName);

    const result = await getClient().createIndex(indexName, docs, { modelId: 'moss-minilm' });
    // Reset cached load promise so next search reloads the freshly built index
    indexLoadPromise = null;
    return {
      success: true as const,
      jobId: result.jobId,
      docCount: result.docCount,
      timeTaken: Date.now() - start,
    };
  } catch (error) {
    return { success: false as const, error: error instanceof Error ? error.message : 'Unknown error' };
  }
}

export async function addMossDocs(indexName: string, docs: DocInput[]) {
  const start = Date.now();
  try {
    const result = await getClient().addDocs(indexName, docs);
    return {
      success: true as const,
      jobId: result.jobId,
      docCount: result.docCount,
      timeTaken: Date.now() - start,
    };
  } catch (error) {
    return { success: false as const, error: error instanceof Error ? error.message : 'Unknown error' };
  }
}

export async function loadMossIndex(indexName: string) {
  const start = Date.now();
  try {
    // Reset cached promise so we always reload a freshly built index
    indexLoadPromise = getClient().loadIndex(indexName);
    await indexLoadPromise;
    return { success: true as const, timeTaken: Date.now() - start };
  } catch (error) {
    indexLoadPromise = null;
    return { success: false as const, error: error instanceof Error ? error.message : 'Unknown error' };
  }
}

export async function searchMoss(query: string, indexName?: string) {
  const targetIndex = indexName || process.env.MOSS_INDEX_NAME;

  if (!process.env.MOSS_PROJECT_ID || !process.env.MOSS_PROJECT_KEY || !targetIndex) {
    throw new Error("Missing Moss credentials in environment variables.");
  }

  try {
    // If index wasn't loaded via the pipeline, fall back to loading it now
    if (!indexLoadPromise) {
      indexLoadPromise = getClient().loadIndex(targetIndex);
    }
    await indexLoadPromise;

    const results = await getClient().query(targetIndex, query, { topK: 5 });
    return {
      success: true as const,
      docs: results.docs.map(doc => ({
        id: doc.id,
        text: doc.text,
        score: doc.score,
        metadata: doc.metadata,
      })),
      timeTaken: results.timeTakenInMs,
    };
  } catch (error) {
    console.error("Moss Search Error:", error);
    return {
      success: false as const,
      error: error instanceof Error ? error.message : "An unknown error occurred",
    };
  }
}

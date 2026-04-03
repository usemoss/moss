'use server'

let MossClient: any = null;
let importError: Error | null = null;

// Lazy load the Moss client to handle missing system dependencies gracefully
async function loadMossClient() {
  if (MossClient) return MossClient;
  if (importError) throw importError;

  try {
    const module = await import("@inferedge/moss");
    MossClient = module.MossClient;
    return MossClient;
  } catch (error) {
    importError = error as Error;
    throw importError;
  }
}

// Module-level singleton — survives across requests in the same server process
let client: any = null;
let indexLoadPromise: Promise<unknown> | null = null;

async function getClient() {
  const projectId = process.env.MOSS_PROJECT_ID;
  const projectKey = process.env.MOSS_PROJECT_KEY;
  if (!projectId || !projectKey) {
    throw new Error("Missing MOSS_PROJECT_ID or MOSS_PROJECT_KEY.");
  }
  if (!client) {
    const MossClientClass = await loadMossClient();
    client = new MossClientClass(projectId, projectKey);
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
    const c = await getClient();
    await c.deleteIndex(indexName);
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

    const c = await getClient();
    const result = await c.createIndex(indexName, docs, { modelId: 'moss-minilm' });
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
    const c = await getClient();
    const result = await c.addDocs(indexName, docs);
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
    const c = await getClient();
    indexLoadPromise = c.loadIndex(indexName);
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
    const c = await getClient();
    // If index wasn't loaded via the pipeline, fall back to loading it now
    if (!indexLoadPromise) {
      indexLoadPromise = c.loadIndex(targetIndex);
    }
    await indexLoadPromise;

    const results = await c.query(targetIndex, query, { topK: 5 });
    return {
      success: true as const,
      docs: results.docs.map((doc: any) => ({
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

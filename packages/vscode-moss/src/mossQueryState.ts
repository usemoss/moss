import type { MossClient } from "@inferedge/moss";
import { createSdkClient } from "./mossClients.js";

let cachedClient:
  | { projectId: string; projectKey: string; client: MossClient }
  | undefined;

/** Which index `loadIndex` last completed successfully for `cachedClient` (local mode). */
let loadedLocalIndexName: string | undefined;

export function getOrCreateSdkClient(
  projectId: string,
  projectKey: string
): MossClient {
  if (
    cachedClient?.projectId === projectId &&
    cachedClient.projectKey === projectKey
  ) {
    return cachedClient.client;
  }
  cachedClient = {
    projectId,
    projectKey,
    client: createSdkClient(projectId, projectKey),
  };
  loadedLocalIndexName = undefined;
  return cachedClient.client;
}

/**
 * Drop the SDK instance (e.g. after API key changes).
 */
export function invalidateSearchSdkCache(): void {
  cachedClient = undefined;
  loadedLocalIndexName = undefined;
}

/**
 * Forget local `loadIndex` so the next local-mode search downloads again (e.g. after reindex).
 */
export function invalidateLoadedSearchIndex(): void {
  loadedLocalIndexName = undefined;
}

export async function ensureLocalIndexLoaded(
  client: MossClient,
  indexName: string
): Promise<void> {
  if (loadedLocalIndexName === indexName) return;
  await client.loadIndex(indexName);
  loadedLocalIndexName = indexName;
}

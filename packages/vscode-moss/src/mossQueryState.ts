import type { MossClient } from "@moss-dev/moss";

/** Tracks which index `loadIndex` last completed for a given `MossClient` session. */
export interface LocalIndexLoadState {
  loadedIndexName?: string;
  /**
   * When `loadIndex` fails for this index name, further attempts in the same session are skipped
   * (avoids repeating download UI and work; `query` still uses cloud fallback). Cleared on success
   * or when the session is reset.
   */
  localLoadFailedIndex?: string;
}

export async function ensureLocalIndexLoaded(
  client: MossClient,
  indexName: string,
  state: LocalIndexLoadState
): Promise<void> {
  if (state.loadedIndexName === indexName) return;
  if (state.localLoadFailedIndex === indexName) return;
  try {
    await client.loadIndex(indexName);
    state.loadedIndexName = indexName;
    state.localLoadFailedIndex = undefined;
  } catch (e: unknown) {
    state.localLoadFailedIndex = indexName;
    throw e;
  }
}

export function clearLocalIndexLoadState(state: LocalIndexLoadState): void {
  state.loadedIndexName = undefined;
  state.localLoadFailedIndex = undefined;
}

const searchIndexStaleHandlers = new Set<() => void>();

/**
 * Register a callback when a full re-index finishes so listeners can reset search state.
 * Returns a disposable; prefer pushing it onto `ExtensionContext.subscriptions`.
 */
export function registerSearchIndexStaleHandler(
  handler: () => void
): { dispose: () => void } {
  searchIndexStaleHandlers.add(handler);
  return {
    dispose: () => {
      searchIndexStaleHandlers.delete(handler);
    },
  };
}

export function notifySearchIndexStale(): void {
  for (const h of searchIndexStaleHandlers) {
    try {
      h();
    } catch {
      /* isolate handler failures */
    }
  }
}

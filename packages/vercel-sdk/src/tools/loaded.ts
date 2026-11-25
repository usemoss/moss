import type { LoadIndexOptions, MossClient } from '@moss-js/moss';

// The client only queries indexes loaded on this device, and a loaded copy does not
// see later addDocs/deleteDocs. Track what these tools loaded, per client, so search
// can load on first use and the mutating tools can reload what search will read.
interface Tracked {
  // Reloads reuse these: loadIndex replaces the options, so dropping them would turn off auto-refresh.
  options?: LoadIndexOptions;
  load: Promise<string>;
  inFlight: boolean;
  // The last reload failed, so the loaded copy may predate a mutation.
  stale: boolean;
}

const trackedByClient = new WeakMap<MossClient, Map<string, Tracked>>();

function trackedFor(client: MossClient) {
  let tracked = trackedByClient.get(client);
  if (!tracked) {
    tracked = new Map();
    trackedByClient.set(client, tracked);
  }
  return tracked;
}

function startLoad(client: MossClient, indexName: string, options?: LoadIndexOptions) {
  const indexes = trackedFor(client);
  const prev = indexes.get(indexName);
  const resolved = options ?? prev?.options;
  // Wait for the previous load so an older copy can't land after a newer one.
  const load = (prev?.load ?? Promise.resolve())
    .catch(() => {})
    .then(() => (resolved ? client.loadIndex(indexName, resolved) : client.loadIndex(indexName)));
  const entry: Tracked = { options: resolved, load, inFlight: true, stale: prev?.stale ?? false };
  indexes.set(indexName, entry);
  load.then(
    () => {
      entry.inFlight = false;
      entry.stale = false;
    },
    () => {
      entry.inFlight = false;
      // Mark the latest entry: a reload queued behind this one hasn't landed yet either.
      (indexes.get(indexName) ?? entry).stale = true;
      // A first load that fails leaves nothing loaded to keep fresh.
      if (!prev && indexes.get(indexName) === entry) indexes.delete(indexName);
    },
  );
  return load;
}

export function loadIndex(client: MossClient, indexName: string, options?: LoadIndexOptions) {
  return startLoad(client, indexName, options);
}

// Concurrent searches share a running load; once it settles, a NOT_FOUND (say after
// the app unloaded the index) starts a new one.
export function loadForSearch(client: MossClient, indexName: string) {
  const entry = trackedFor(client).get(indexName);
  return entry?.inFlight ? entry.load : startLoad(client, indexName);
}

export function isStale(client: MossClient, indexName: string) {
  return trackedFor(client).get(indexName)?.stale ?? false;
}

export async function reloadIfLoaded(client: MossClient, indexName: string) {
  if (!trackedFor(client).has(indexName)) return;
  // The mutation already succeeded; a failed reload marks the index stale for search to retry.
  await startLoad(client, indexName).catch(() => {});
}

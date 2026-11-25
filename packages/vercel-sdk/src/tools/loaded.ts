import type { MossClient } from '@moss-js/moss';

// The client only queries indexes loaded on this device, and a loaded copy does not
// see later addDocs/deleteDocs. Track what these tools loaded, per client, so search
// can load on first use and the mutating tools can reload what search will read.
const loadedByClient = new WeakMap<MossClient, Map<string, Promise<unknown>>>();

function loadedFor(client: MossClient) {
  let loaded = loadedByClient.get(client);
  if (!loaded) {
    loaded = new Map();
    loadedByClient.set(client, loaded);
  }
  return loaded;
}

function track(client: MossClient, indexName: string, load: Promise<unknown>) {
  const loaded = loadedFor(client);
  const tracked = load.catch((err: unknown) => {
    if (loaded.get(indexName) === tracked) loaded.delete(indexName);
    throw err;
  });
  loaded.set(indexName, tracked);
  return tracked;
}

export function ensureLoaded(client: MossClient, indexName: string) {
  return loadedFor(client).get(indexName) ?? track(client, indexName, client.loadIndex(indexName));
}

export function recordLoad<T>(client: MossClient, indexName: string, load: Promise<T>): Promise<T> {
  return track(client, indexName, load) as Promise<T>;
}

export async function reloadIfLoaded(client: MossClient, indexName: string) {
  if (!loadedFor(client).has(indexName)) return;
  // The mutation already succeeded; a failed reload only drops the record.
  await track(client, indexName, client.loadIndex(indexName)).catch(() => {});
}

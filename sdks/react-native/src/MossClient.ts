import { SharedObject } from 'expo-modules-core';

import MossModule from './MossModule';
import type {
  CreateIndexOptions,
  DocumentInfo,
  IndexInfo,
  LoadIndexOptions,
  MutationOptions,
  MutationResult,
  QueryOptions,
  SearchResult,
} from './types';
import { MossError } from './types';

type NativeClient = SharedObject & {
  createIndex(name: string, docsJson: string, modelId: string | null): Promise<MutationResult>;
  loadIndex(name: string, options: Record<string, unknown>): Promise<void>;
  unloadIndex(name: string): Promise<void>;
  query(name: string, query: string, options: Record<string, unknown>): Promise<SearchResult>;
  listIndexes(): Promise<IndexInfo[]>;
  getIndex(name: string): Promise<IndexInfo>;
  deleteIndex(name: string): Promise<boolean>;
  addDocs(name: string, docsJson: string, upsert: boolean): Promise<MutationResult>;
  close(): void;
};

declare class NativeMossClient extends SharedObject {
  constructor(projectId: string, projectKey: string);
}

const NativeMossClientCtor = (MossModule as { MossClient: typeof NativeMossClient }).MossClient;

const DEFAULT_MODEL_ID = 'moss-minilm';

/**
 * On-device Moss client for React Native / Expo.
 *
 * iOS uses the native `Moss.xcframework` (same binary as the Swift SDK).
 * Android support is tracked in https://github.com/usemoss/moss/issues/411 —
 * constructing a client on Android throws until a native Android build ships.
 *
 * Requires a development build or Expo prebuild — custom native code does not
 * run in Expo Go.
 *
 * @example
 * ```ts
 * import { MossClient } from '@moss-dev/moss-react-native';
 *
 * const client = new MossClient(projectId, projectKey);
 * try {
 *   await client.createIndex('docs', [
 *     { id: '1', text: 'Refunds take 3-5 business days.' },
 *   ]);
 *   await client.loadIndex('docs');
 *   const result = await client.query('docs', 'how long do refunds take?');
 *   console.log(result.docs);
 * } finally {
 *   client.close();
 * }
 * ```
 */
export class MossClient {
  readonly #native: NativeClient;

  constructor(projectId: string, projectKey: string) {
    if (!projectId || !projectKey) {
      throw new MossError(-2, 'projectId and projectKey are required');
    }
    try {
      this.#native = new NativeMossClientCtor(projectId, projectKey) as unknown as NativeClient;
    } catch (err) {
      throw wrapNativeError(err);
    }
  }

  /** Native SDK version string from `moss_sdk_version()`. */
  static get sdkVersion(): string {
    return String((MossModule as { sdkVersion?: string }).sdkVersion ?? 'unknown');
  }

  /**
   * Override the embedding-model cache directory.
   * Call before constructing any `MossClient` if you need a custom location
   * (e.g. an App Group container). iOS defaults to Library/Caches/moss-models.
   */
  static async setModelCacheDir(path: string): Promise<void> {
    try {
      await (MossModule as { setModelCacheDir(path: string): Promise<void> }).setModelCacheDir(path);
    } catch (err) {
      throw wrapNativeError(err);
    }
  }

  async createIndex(
    indexName: string,
    docs: DocumentInfo[],
    options?: CreateIndexOptions,
  ): Promise<MutationResult> {
    const hasEmbeddings = docs.some((d) => Array.isArray(d.embedding) && d.embedding.length > 0);
    const modelId = options?.modelId ?? (hasEmbeddings ? 'custom' : DEFAULT_MODEL_ID);
    const docsJson = serializeDocs(docs);
    try {
      return await this.#native.createIndex(indexName, docsJson, modelId);
    } catch (err) {
      throw wrapNativeError(err);
    }
  }

  async loadIndex(indexName: string, options?: LoadIndexOptions): Promise<void> {
    try {
      await this.#native.loadIndex(indexName, {
        autoRefresh: options?.autoRefresh ?? false,
        pollingIntervalSeconds: options?.pollingIntervalSeconds ?? 600,
        cachePath: options?.cachePath ?? null,
      });
    } catch (err) {
      throw wrapNativeError(err);
    }
  }

  async unloadIndex(indexName: string): Promise<void> {
    try {
      await this.#native.unloadIndex(indexName);
    } catch (err) {
      throw wrapNativeError(err);
    }
  }

  /**
   * Search a loaded index.
   *
   * Indexes built from custom document embeddings have no on-device model to
   * embed `query` with — pass `options.embedding` with a matching query vector
   * for those. Text-model indexes ignore it.
   */
  async query(indexName: string, query: string, options?: QueryOptions): Promise<SearchResult> {
    const filterJson = resolveFilterJson(options);
    try {
      return await this.#native.query(indexName, query, {
        topK: options?.topK ?? 5,
        alpha: options?.alpha ?? 0.8,
        filterJson,
        embedding: options?.embedding ?? null,
      });
    } catch (err) {
      throw wrapNativeError(err);
    }
  }

  async listIndexes(): Promise<IndexInfo[]> {
    try {
      return await this.#native.listIndexes();
    } catch (err) {
      throw wrapNativeError(err);
    }
  }

  async getIndex(indexName: string): Promise<IndexInfo> {
    try {
      return await this.#native.getIndex(indexName);
    } catch (err) {
      throw wrapNativeError(err);
    }
  }

  async deleteIndex(indexName: string): Promise<boolean> {
    try {
      return await this.#native.deleteIndex(indexName);
    } catch (err) {
      throw wrapNativeError(err);
    }
  }

  async addDocs(
    indexName: string,
    docs: DocumentInfo[],
    options?: MutationOptions,
  ): Promise<MutationResult> {
    const docsJson = serializeDocs(docs);
    try {
      return await this.#native.addDocs(indexName, docsJson, options?.upsert ?? true);
    } catch (err) {
      throw wrapNativeError(err);
    }
  }

  /** Release the native client. Safe to call more than once. */
  close(): void {
    try {
      this.#native.close();
    } catch {
      // already closed
    }
  }
}

/** Largest finite 32-bit float; the native side stores embeddings as `Float`. */
const MAX_FLOAT32 = 3.4028234663852886e38;

/**
 * Serializes documents for the native layer.
 *
 * `JSON.stringify` turns `NaN` / `±Infinity` into `null`, so an embedding
 * containing either would reach the engine silently corrupted rather than
 * rejected. Values beyond the 32-bit float range are also refused, since the
 * native side narrows to `Float` and would round them to infinity.
 */
function serializeDocs(docs: DocumentInfo[]): string {
  if (!Array.isArray(docs)) {
    throw new MossError(-2, 'docs must be an array');
  }
  for (const doc of docs) {
    const embedding = doc?.embedding;
    if (embedding === undefined) continue;
    if (!Array.isArray(embedding)) {
      throw new MossError(-2, `embedding for doc "${doc?.id}" must be an array of numbers`);
    }
    for (const value of embedding) {
      if (typeof value !== 'number' || !Number.isFinite(value) || Math.abs(value) > MAX_FLOAT32) {
        throw new MossError(
          -2,
          `embedding for doc "${doc?.id}" must contain only finite 32-bit-float values`,
        );
      }
    }
  }
  try {
    return JSON.stringify(docs);
  } catch (err) {
    throw new MossError(-2, `docs are not JSON-serializable: ${String(err)}`);
  }
}

/**
 * Resolves the metadata filter to the engine's JSON form.
 *
 * `filter` is the shape `@moss-dev/moss` uses, so callers migrating from the
 * Node SDK reach for it first. Silently ignoring it would run the query
 * unfiltered and return documents outside the intended scope, so an
 * unserializable filter is an error rather than a fallback to `null`.
 */
function resolveFilterJson(options?: QueryOptions): string | null {
  if (options?.filter !== undefined && options?.filterJson !== undefined) {
    throw new MossError(-2, 'Pass either `filter` or `filterJson`, not both');
  }
  if (options?.filter !== undefined) {
    let encoded: string;
    try {
      encoded = JSON.stringify(options.filter);
    } catch (err) {
      throw new MossError(-2, `filter is not JSON-serializable: ${String(err)}`);
    }
    if (typeof encoded !== 'string') {
      throw new MossError(-2, 'filter is not JSON-serializable');
    }
    return encoded;
  }
  return options?.filterJson ?? null;
}

function wrapNativeError(err: unknown): Error {
  if (err instanceof MossError) return err;
  if (err && typeof err === 'object') {
    const e = err as { code?: number; message?: string };
    const message = typeof e.message === 'string' ? e.message : String(err);
    const code = typeof e.code === 'number' ? e.code : -1;
    return new MossError(code, message);
  }
  return new MossError(-1, String(err));
}

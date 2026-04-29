---
title: "MossClient (JS)"
---

[**@moss-dev/moss-web v1.0.0**](../README.md)

***

[@moss-dev/moss-web](../globals.md) / MossClient

# Class: MossClient

MossClient - Async-first semantic search client for vector similarity operations.

All mutations (createIndex, addDocs, deleteDocs) are async operations
that run server-side and poll until complete.

## Example

```typescript
import { MossClient } from '@moss-dev/moss-web';

const client = new MossClient('your-project-id', 'your-project-key');

// Create an index with documents (polls until complete)
const result = await client.createIndex('docs', [
  { id: '1', text: 'Machine learning fundamentals' },
  { id: '2', text: 'Deep learning neural networks' }
]);

// Add docs (polls until complete)
await client.addDocs('docs', [
  { id: '3', text: 'Natural language processing' }
]);

// Query the index
await client.loadIndex('docs');
const results = await client.query('docs', 'AI and neural networks');
```

## Constructors

### Constructor

> **new MossClient**(`projectId`, `projectKey`): `MossClient`

Creates a new MossClient instance.

#### Parameters

| Parameter | Type | Description |
| ------ | ------ | ------ |
| `projectId` | `string` | Your project identifier. |
| `projectKey` | `string` | Your project authentication key. |

#### Returns

`MossClient`

## Methods

### createIndex()

> **createIndex**(`indexName`, `docs`, `options?`): `Promise`\<[`MutationResult`](../interfaces/MutationResult.md)\>

Creates a new index with the provided documents via async upload.

Handles the full flow: init → upload → build → poll until complete.
Returns when the index is ready.

When all documents have pre-computed embeddings, they are serialized as raw
float32 in the binary upload. When no documents have embeddings, the server
generates embeddings in batches (dimension=0 flow).

Mixed documents (some with embeddings, some without) are rejected.

#### Parameters

| Parameter | Type | Description |
| ------ | ------ | ------ |
| `indexName` | `string` | Name of the index to create. |
| `docs` | [`DocumentInfo`](../interfaces/DocumentInfo.md)[] | Documents, optionally with pre-computed embeddings. |
| `options?` | [`CreateIndexOptions`](../interfaces/CreateIndexOptions.md) | Optional model ID and progress callback. |

#### Returns

`Promise`\<[`MutationResult`](../interfaces/MutationResult.md)\>

Promise that resolves to MutationResult when the index is ready.

#### Throws

If the index already exists or creation fails.

#### Example

```typescript
const result = await client.createIndex('knowledge-base', [
  { id: 'doc1', text: 'Introduction to AI' },
  { id: 'doc2', text: 'Machine learning basics' }
], {
  onProgress: (p) => console.log(`${p.status} ${p.progress}%`),
});
```

***

### getIndex()

> **getIndex**(`indexName`): `Promise`\<[`IndexInfo`](../interfaces/IndexInfo.md)\>

Gets information about a specific index.

#### Parameters

| Parameter | Type | Description |
| ------ | ------ | ------ |
| `indexName` | `string` | Name of the index to retrieve. |

#### Returns

`Promise`\<[`IndexInfo`](../interfaces/IndexInfo.md)\>

Promise that resolves to IndexInfo object.

#### Throws

If the index does not exist.

#### Example

```typescript
const info = await client.getIndex('knowledge-base');
console.log(`Index has ${info.docCount} documents`);
```

***

### listIndexes()

> **listIndexes**(): `Promise`\<[`IndexInfo`](../interfaces/IndexInfo.md)[]\>

Lists all available indexes.

#### Returns

`Promise`\<[`IndexInfo`](../interfaces/IndexInfo.md)[]\>

Promise that resolves to array of IndexInfo objects.

#### Example

```typescript
const indexes = await client.listIndexes();
indexes.forEach(index => {
  console.log(`${index.name}: ${index.docCount} docs`);
});
```

***

### deleteIndex()

> **deleteIndex**(`indexName`): `Promise`\<`boolean`\>

Deletes an index and all its data.

#### Parameters

| Parameter | Type | Description |
| ------ | ------ | ------ |
| `indexName` | `string` | Name of the index to delete. |

#### Returns

`Promise`\<`boolean`\>

Promise that resolves to true if successful.

#### Throws

If the index does not exist.

#### Example

```typescript
const deleted = await client.deleteIndex('old-index');
```

***

### addDocs()

> **addDocs**(`indexName`, `docs`, `options?`): `Promise`\<[`MutationResult`](../interfaces/MutationResult.md)\>

Adds or updates documents in an index asynchronously.

The index rebuild happens server-side. This method polls until
the rebuild is complete and then returns.

#### Parameters

| Parameter | Type | Description |
| ------ | ------ | ------ |
| `indexName` | `string` | Name of the target index. |
| `docs` | [`DocumentInfo`](../interfaces/DocumentInfo.md)[] | Documents to add or update. |
| `options?` | [`MutationOptions`](../interfaces/MutationOptions.md) | Optional configuration (upsert, onProgress callback). |

#### Returns

`Promise`\<[`MutationResult`](../interfaces/MutationResult.md)\>

Promise that resolves to MutationResult when the operation is complete.

#### Throws

If the index does not exist.

#### Example

```typescript
const result = await client.addDocs('knowledge-base', [
  { id: 'new-doc', text: 'New content to index' }
], { upsert: true });
console.log(`Job ${result.jobId} completed`);
```

***

### deleteDocs()

> **deleteDocs**(`indexName`, `docIds`, `options?`): `Promise`\<[`MutationResult`](../interfaces/MutationResult.md)\>

Deletes documents from an index by their IDs asynchronously.

The index rebuild happens server-side. This method polls until
the rebuild is complete and then returns.

#### Parameters

| Parameter | Type | Description |
| ------ | ------ | ------ |
| `indexName` | `string` | Name of the target index. |
| `docIds` | `string`[] | Array of document IDs to delete. |
| `options?` | [`MutationOptions`](../interfaces/MutationOptions.md) | Optional configuration (onProgress callback). |

#### Returns

`Promise`\<[`MutationResult`](../interfaces/MutationResult.md)\>

Promise that resolves to MutationResult when the operation is complete.

#### Throws

If the index does not exist.

#### Example

```typescript
const result = await client.deleteDocs('knowledge-base', ['doc1', 'doc2']);
console.log(`Job ${result.jobId} completed`);
```

***

### getJobStatus()

> **getJobStatus**(`jobId`): `Promise`\<[`JobStatusResponse`](../interfaces/JobStatusResponse.md)\>

Gets the current status of an async job.

#### Parameters

| Parameter | Type | Description |
| ------ | ------ | ------ |
| `jobId` | `string` | The job ID returned by createIndex, addDocs, or deleteDocs. |

#### Returns

`Promise`\<[`JobStatusResponse`](../interfaces/JobStatusResponse.md)\>

Promise that resolves to JobStatusResponse with progress details.

#### Example

```typescript
const status = await client.getJobStatus(jobId);
console.log(`${status.status} — ${status.progress}%`);
```

***

### getDocs()

> **getDocs**(`indexName`, `options?`): `Promise`\<[`DocumentInfo`](../interfaces/DocumentInfo.md)[]\>

Retrieves documents from an index.

#### Parameters

| Parameter | Type | Description |
| ------ | ------ | ------ |
| `indexName` | `string` | Name of the target index. |
| `options?` | [`GetDocumentsOptions`](../interfaces/GetDocumentsOptions.md) | Optional configuration for retrieval. |

#### Returns

`Promise`\<[`DocumentInfo`](../interfaces/DocumentInfo.md)[]\>

Promise that resolves to array of documents.

#### Throws

If the index does not exist.

#### Example

```typescript
// Get all documents
const allDocs = await client.getDocs('knowledge-base');

// Get specific documents
const specificDocs = await client.getDocs('knowledge-base', {
  docIds: ['doc1', 'doc2']
});
```

***

### loadIndex()

> **loadIndex**(`indexName`, `options?`): `Promise`\<`string`\>

Downloads an index from the cloud into memory for fast local querying.

**How it works:**
1. Fetches the index assets from the cloud
2. Loads the embedding model for generating query embeddings
3. Executes a local similarity match between the query embedding and the retrieved index.

**Why use this?**
- Without `loadIndex()`: Every `query()` call goes to the cloud API (~100-500ms network latency)
- With `loadIndex()`: Queries run entirely in-memory (~1-10ms)

**Reload behavior:**
If the index is already loaded, calling `loadIndex()` again will:
- Stop any existing auto-refresh polling
- Download a fresh copy from the cloud
- Replace the in-memory index

**Auto-refresh (optional):**
Enable `autoRefresh: true` to periodically poll the cloud for updates.
When a newer version is detected, the index is automatically hot-swapped
without interrupting queries.

#### Parameters

| Parameter | Type | Description |
| ------ | ------ | ------ |
| `indexName` | `string` | Name of the index to load. |
| `options?` | [`LoadIndexOptions`](../interfaces/LoadIndexOptions.md) | Optional configuration including auto-refresh settings. |

#### Returns

`Promise`\<`string`\>

Promise that resolves to the index name.

#### Throws

If the index does not exist in the cloud or loading fails.

#### Example

```typescript
// Simple load - enables fast local queries
await client.loadIndex('my-index');

// Now queries run locally (fast, no network calls)
const results = await client.query('my-index', 'search text');

// Load with auto-refresh to keep index up-to-date
await client.loadIndex('my-index', {
  autoRefresh: true,
  pollingIntervalInSeconds: 300, // Check cloud every 5 minutes
});

// Stop auto-refresh by reloading without the option
await client.loadIndex('my-index');
```

***

### query()

> **query**(`indexName`, `query`, `options?`): `Promise`\<[`SearchResult`](../interfaces/SearchResult.md)\>

Performs a semantic similarity search against the specified index.

If the index has been loaded via `loadIndex()`, runs entirely in-memory.
Otherwise, falls back to the cloud `/query` endpoint.

#### Parameters

| Parameter | Type | Description |
| ------ | ------ | ------ |
| `indexName` | `string` | Name of the target index to search. |
| `query` | `string` | The search query text. |
| `options?` | [`QueryOptions`](../interfaces/QueryOptions.md) | Optional query configuration including topK (default: 5) and embedding overrides. |

#### Returns

`Promise`\<[`SearchResult`](../interfaces/SearchResult.md)\>

Promise that resolves to SearchResult with matching documents.

#### Throws

If the specified index does not exist.

#### Example

```typescript
const results = await client.query('knowledge-base', 'machine learning');
results.docs.forEach(doc => {
  console.log(`${doc.id}: ${doc.text} (score: ${doc.score})`);
});
```

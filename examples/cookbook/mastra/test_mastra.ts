/**
 * Unit tests for Moss + Mastra tool execute functions.
 * Runs with: tsx --test test_mastra.ts
 */

import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { executeMossSearch, executeMossIndex, type MossClientLike } from './moss_mastra';

function makeMockClient(overrides: Partial<MossClientLike> = {}): MossClientLike {
  return {
    query: async () => ({ docs: [], timeTakenInMs: 0 }),
    addDocs: async () => {},
    ...overrides,
  };
}

describe('executeMossSearch', () => {
  it('maps docs to { content, score } shape', async () => {
    const client = makeMockClient({
      query: async () => ({
        docs: [
          { text: 'hello world', score: 0.9 },
          { text: 'foo bar', score: 0.7 },
        ],
        timeTakenInMs: 4,
      }),
    });

    const result = await executeMossSearch(client, 'my-index', 'test query');

    assert.equal(result.results.length, 2);
    assert.deepEqual(result.results[0], { content: 'hello world', score: 0.9 });
    assert.deepEqual(result.results[1], { content: 'foo bar', score: 0.7 });
    assert.equal(result.timeTakenInMs, 4);
  });

  it('returns empty results array when no docs found', async () => {
    const client = makeMockClient();
    const result = await executeMossSearch(client, 'my-index', 'nothing here');
    assert.deepEqual(result.results, []);
    assert.equal(result.timeTakenInMs, 0);
  });

  it('passes correct index name, query, and topK to client.query', async () => {
    const calls: Array<{ index: string; query: string; opts: { topK: number } }> = [];
    const client = makeMockClient({
      query: async (index, query, opts) => {
        calls.push({ index, query, opts });
        return { docs: [], timeTakenInMs: 0 };
      },
    });

    await executeMossSearch(client, 'test-index', 'my query');

    assert.equal(calls.length, 1, 'query should be called exactly once');
    assert.equal(calls[0].index, 'test-index');
    assert.equal(calls[0].query, 'my query');
    assert.equal(calls[0].opts.topK, 3);
  });
});

describe('executeMossIndex', () => {
  it('returns { success: true } with provided docId', async () => {
    const client = makeMockClient();
    const result = await executeMossIndex(client, 'my-index', 'some text', 'custom-id');
    assert.deepEqual(result, { success: true, docId: 'custom-id' });
  });

  it('generates a docId starting with "doc_" when none is provided', async () => {
    const client = makeMockClient();
    const result = await executeMossIndex(client, 'my-index', 'some text');
    assert.equal(result.success, true);
    assert.ok(result.docId.startsWith('doc_'), `expected docId to start with "doc_", got "${result.docId}"`);
  });

  it('calls addDocs with correct index, document, and upsert flag', async () => {
    const calls: Array<{ index: string; docs: Array<{ id: string; text: string }>; opts: { upsert: boolean } }> = [];
    const client = makeMockClient({
      addDocs: async (index, docs, opts) => {
        calls.push({ index, docs, opts });
      },
    });

    await executeMossIndex(client, 'test-index', 'hello text', 'my-doc');

    assert.equal(calls.length, 1, 'addDocs should be called exactly once');
    assert.equal(calls[0].index, 'test-index');
    assert.deepEqual(calls[0].docs, [{ id: 'my-doc', text: 'hello text' }]);
    assert.deepEqual(calls[0].opts, { upsert: true });
  });
});

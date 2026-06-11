/**
 * Unit tests for Moss + Vercel AI SDK integration.
 * Runs with: tsx --test test_vercel.ts
 * No real API credentials required.
 */

import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { createMossTools } from './moss_vercel.js';

function makeMockClient(overrides: Record<string, unknown> = {}) {
  return {
    loadIndex: async (_name: string) => {},
    query: async () => ({
      docs: [],
      query: '',
      indexName: 'test-index',
      timeTakenInMs: 0,
    }),
    ...overrides,
  } as any;
}

describe('createMossTools', () => {
  it('calls loadIndex with the correct index name', async () => {
    const calls: string[] = [];
    const client = makeMockClient({
      loadIndex: async (name: string) => { calls.push(name); },
    });

    await createMossTools(client, 'my-index');

    assert.equal(calls.length, 1, 'loadIndex should be called exactly once');
    assert.equal(calls[0], 'my-index');
  });

  it('returns an object with search and loadIndex tools', async () => {
    const client = makeMockClient();
    const tools = await createMossTools(client, 'my-index');

    assert.ok('search' in tools, 'tools should have a search key');
    assert.ok('loadIndex' in tools, 'tools should have a loadIndex key');
    assert.equal(typeof tools.search.execute, 'function');
    assert.equal(typeof tools.loadIndex.execute, 'function');
  });

  it('search tool forwards query and topK to client.query', async () => {
    const calls: Array<{ index: string; query: string; opts: { topK: number } }> = [];
    const client = makeMockClient({
      query: async (index: string, query: string, opts: { topK: number }) => {
        calls.push({ index, query, opts });
        return { docs: [], query, indexName: index, timeTakenInMs: 1 };
      },
    });

    const tools = await createMossTools(client, 'test-index');
    await tools.search.execute(
      { query: 'what is the refund policy?', topK: 3 },
      { toolCallId: 'call-1', messages: [], abortSignal: new AbortController().signal },
    );

    assert.equal(calls.length, 1, 'query should be called exactly once');
    assert.equal(calls[0].index, 'test-index');
    assert.equal(calls[0].query, 'what is the refund policy?');
    assert.equal(calls[0].opts.topK, 3);
  });

  it('search tool returns docs from client.query', async () => {
    const client = makeMockClient({
      query: async () => ({
        docs: [
          { id: 'doc1', text: 'Refunds take 3-5 business days.', score: 0.95, metadata: {} },
          { id: 'doc2', text: 'Returns are accepted within 30 days.', score: 0.88, metadata: {} },
        ],
        query: 'refund',
        indexName: 'test-index',
        timeTakenInMs: 4,
      }),
    });

    const tools = await createMossTools(client, 'test-index');
    const result = await tools.search.execute(
      { query: 'refund', topK: 5 },
      { toolCallId: 'call-2', messages: [], abortSignal: new AbortController().signal },
    );

    assert.equal(result.docs.length, 2);
    assert.equal(result.docs[0].text, 'Refunds take 3-5 business days.');
    assert.equal(result.docs[1].text, 'Returns are accepted within 30 days.');
  });
});

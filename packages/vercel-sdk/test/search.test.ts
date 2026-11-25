import { describe, it, expect, vi } from 'vitest';
import { mossSearchTool } from '../src/tools/search.js';

function createMockClient() {
  return {
    query: vi.fn().mockResolvedValue({
      docs: [
        { id: 'doc1', text: 'result text', score: 0.95, metadata: {} },
      ],
      query: 'test query',
      indexName: 'test-index',
      timeTakenInMs: 5,
    }),
    createIndex: vi.fn(),
    getIndex: vi.fn(),
    listIndexes: vi.fn(),
    deleteIndex: vi.fn(),
    addDocs: vi.fn(),
    deleteDocs: vi.fn(),
    getJobStatus: vi.fn(),
    getDocs: vi.fn(),
    loadIndex: vi.fn(),
  } as any;
}

describe('mossSearchTool', () => {
  it('creates a tool with prebound indexName', () => {
    const client = createMockClient();
    const searchTool = mossSearchTool({
      client,
      indexName: 'my-index',
    });

    expect(searchTool.description).toContain('Search');
    expect(searchTool.inputSchema).toBeDefined();
  });

  it('executes search with prebound indexName', async () => {
    const client = createMockClient();
    const searchTool = mossSearchTool({
      client,
      indexName: 'my-index',
    });

    const result = await searchTool.execute!(
      { query: 'test query', topK: 5 },
      { toolCallId: 'call-1', messages: [], abortSignal: new AbortController().signal },
    );

    expect(client.query).toHaveBeenCalledWith('my-index', 'test query', {
      topK: 5,
    });
    expect(result).toHaveProperty('docs');
  });

  it('executes search with indexName from input when not prebound', async () => {
    const client = createMockClient();
    const searchTool = mossSearchTool({ client });

    await searchTool.execute!(
      { indexName: 'dynamic-index', query: 'test', topK: 10 } as any,
      { toolCallId: 'call-1', messages: [], abortSignal: new AbortController().signal },
    );

    expect(client.query).toHaveBeenCalledWith('dynamic-index', 'test', {
      topK: 10,
    });
  });

  it('loads an unloaded index once, then retries the query', async () => {
    const client = createMockClient();
    const notLoaded = Object.assign(new Error('not loaded'), { code: 'NOT_FOUND' });
    client.query
      .mockRejectedValueOnce(notLoaded)
      .mockRejectedValueOnce(notLoaded);
    client.loadIndex.mockResolvedValue('my-index');
    const searchTool = mossSearchTool({ client, indexName: 'my-index' });
    const opts = { toolCallId: 'call-1', messages: [], abortSignal: new AbortController().signal };

    const results = await Promise.all([
      searchTool.execute!({ query: 'a', topK: 5 }, opts),
      searchTool.execute!({ query: 'b', topK: 5 }, opts),
    ]);

    expect(client.loadIndex).toHaveBeenCalledTimes(1);
    expect(client.loadIndex).toHaveBeenCalledWith('my-index');
    expect(client.query).toHaveBeenCalledTimes(4);
    expect(results[0]).toHaveProperty('docs');
    expect(results[1]).toHaveProperty('docs');
  });

  it('loads the index again when it is no longer loaded', async () => {
    const client = createMockClient();
    const notLoaded = Object.assign(new Error('not loaded'), { code: 'NOT_FOUND' });
    client.query
      .mockRejectedValueOnce(notLoaded)
      .mockResolvedValueOnce({ docs: [] })
      .mockRejectedValueOnce(notLoaded);
    client.loadIndex.mockResolvedValue('my-index');
    const searchTool = mossSearchTool({ client, indexName: 'my-index' });
    const opts = { toolCallId: 'call-1', messages: [], abortSignal: new AbortController().signal };

    await searchTool.execute!({ query: 'a', topK: 5 }, opts);
    const result = await searchTool.execute!({ query: 'b', topK: 5 }, opts);

    expect(client.loadIndex).toHaveBeenCalledTimes(2);
    expect(result).toHaveProperty('docs');
  });

  it('does not load the index for other errors', async () => {
    const client = createMockClient();
    client.query.mockRejectedValueOnce(Object.assign(new Error('nope'), { code: 'UNAUTHORIZED' }));
    const searchTool = mossSearchTool({ client, indexName: 'my-index' });

    await expect(
      searchTool.execute!(
        { query: 'a', topK: 5 },
        { toolCallId: 'call-1', messages: [], abortSignal: new AbortController().signal },
      ),
    ).rejects.toThrow('nope');
    expect(client.loadIndex).not.toHaveBeenCalled();
  });

  it('accepts a custom description', () => {
    const client = createMockClient();
    const searchTool = mossSearchTool({
      client,
      description: 'Custom search description',
    });

    expect(searchTool.description).toBe('Custom search description');
  });
});

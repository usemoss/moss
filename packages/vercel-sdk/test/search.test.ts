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

  it('accepts a custom description', () => {
    const client = createMockClient();
    const searchTool = mossSearchTool({
      client,
      description: 'Custom search description',
    });

    expect(searchTool.description).toBe('Custom search description');
  });
});

import { describe, it, expect, vi } from 'vitest';
import { mossAddDocsTool, mossDeleteDocsTool } from '../src/tools/docs.js';
import { mossSearchTool } from '../src/tools/search.js';

function createMockClient() {
  return {
    query: vi.fn(),
    createIndex: vi.fn(),
    getIndex: vi.fn(),
    listIndexes: vi.fn(),
    deleteIndex: vi.fn(),
    addDocs: vi.fn().mockResolvedValue({ indexName: 'test-index', docsAdded: 1 }),
    deleteDocs: vi.fn().mockResolvedValue({ indexName: 'test-index', docsDeleted: 1 }),
    getJobStatus: vi.fn(),
    getDocs: vi.fn(),
    loadIndex: vi.fn(),
  } as any;
}

const toolCallContext = {
  toolCallId: 'call-1',
  messages: [],
  abortSignal: new AbortController().signal,
};

describe('mossAddDocsTool', () => {
  it('creates a tool with prebound indexName', () => {
    const client = createMockClient();
    const tool = mossAddDocsTool({ client, indexName: 'my-index' });

    expect(tool.description).toContain('Add documents');
    expect(tool.inputSchema).toBeDefined();
  });

  it('executes with prebound indexName', async () => {
    const client = createMockClient();
    const tool = mossAddDocsTool({ client, indexName: 'my-index' });

    const docs = [{ id: 'doc1', text: 'hello world' }];
    await tool.execute!({ docs }, toolCallContext);

    expect(client.addDocs).toHaveBeenCalledWith('my-index', docs);
  });

  it('executes with indexName from input when not prebound', async () => {
    const client = createMockClient();
    const tool = mossAddDocsTool({ client });

    const docs = [{ id: 'doc1', text: 'hello world' }];
    await tool.execute!(
      { indexName: 'dynamic-index', docs } as any,
      toolCallContext,
    );

    expect(client.addDocs).toHaveBeenCalledWith('dynamic-index', docs);
  });

  it('sets needsApproval to true', () => {
    const client = createMockClient();
    const tool = mossAddDocsTool({ client });

    expect(tool.needsApproval).toBe(true);
  });

  it('accepts a custom description', () => {
    const client = createMockClient();
    const tool = mossAddDocsTool({ client, description: 'Custom add' });

    expect(tool.description).toBe('Custom add');
  });
});

describe('mossDeleteDocsTool', () => {
  it('creates a tool with prebound indexName', () => {
    const client = createMockClient();
    const tool = mossDeleteDocsTool({ client, indexName: 'my-index' });

    expect(tool.description).toContain('Delete documents');
    expect(tool.inputSchema).toBeDefined();
  });

  it('executes with prebound indexName', async () => {
    const client = createMockClient();
    const tool = mossDeleteDocsTool({ client, indexName: 'my-index' });

    await tool.execute!({ docIds: ['doc1', 'doc2'] }, toolCallContext);

    expect(client.deleteDocs).toHaveBeenCalledWith('my-index', ['doc1', 'doc2']);
  });

  it('executes with indexName from input when not prebound', async () => {
    const client = createMockClient();
    const tool = mossDeleteDocsTool({ client });

    await tool.execute!(
      { indexName: 'dynamic-index', docIds: ['doc1'] } as any,
      toolCallContext,
    );

    expect(client.deleteDocs).toHaveBeenCalledWith('dynamic-index', ['doc1']);
  });

  it('sets needsApproval to true', () => {
    const client = createMockClient();
    const tool = mossDeleteDocsTool({ client });

    expect(tool.needsApproval).toBe(true);
  });

  it('accepts a custom description', () => {
    const client = createMockClient();
    const tool = mossDeleteDocsTool({ client, description: 'Custom delete' });

    expect(tool.description).toBe('Custom delete');
  });
});

describe('reloading after mutations', () => {
  it('reloads an index the search tool loaded, so search sees the change', async () => {
    const client = createMockClient();
    client.query
      .mockRejectedValueOnce(Object.assign(new Error('not loaded'), { code: 'NOT_FOUND' }))
      .mockResolvedValue({ docs: [] });
    client.loadIndex.mockResolvedValue('my-index');
    const search = mossSearchTool({ client, indexName: 'my-index' });
    const addDocs = mossAddDocsTool({ client, indexName: 'my-index' });
    const deleteDocs = mossDeleteDocsTool({ client, indexName: 'my-index' });

    await search.execute!({ query: 'q', topK: 5 }, toolCallContext);
    expect(client.loadIndex).toHaveBeenCalledTimes(1);

    await addDocs.execute!({ docs: [{ id: 'doc1', text: 'hello' }] }, toolCallContext);
    expect(client.loadIndex).toHaveBeenCalledTimes(2);

    await deleteDocs.execute!({ docIds: ['doc1'] }, toolCallContext);
    expect(client.loadIndex).toHaveBeenCalledTimes(3);
  });

  it('does not load an index the tools never loaded', async () => {
    const client = createMockClient();
    const addDocs = mossAddDocsTool({ client, indexName: 'my-index' });

    await addDocs.execute!({ docs: [{ id: 'doc1', text: 'hello' }] }, toolCallContext);

    expect(client.loadIndex).not.toHaveBeenCalled();
  });

  it('still returns the mutation result when the reload fails', async () => {
    const client = createMockClient();
    client.query
      .mockRejectedValueOnce(Object.assign(new Error('not loaded'), { code: 'NOT_FOUND' }))
      .mockResolvedValue({ docs: [] });
    client.loadIndex.mockResolvedValueOnce('my-index').mockRejectedValueOnce(new Error('download failed'));
    await mossSearchTool({ client, indexName: 'my-index' }).execute!({ query: 'q', topK: 5 }, toolCallContext);

    const result = await mossAddDocsTool({ client, indexName: 'my-index' }).execute!(
      { docs: [{ id: 'doc1', text: 'hello' }] },
      toolCallContext,
    );

    expect(result).toEqual({ indexName: 'test-index', docsAdded: 1 });
  });
});

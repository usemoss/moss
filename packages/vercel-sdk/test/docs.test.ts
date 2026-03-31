import { describe, it, expect, vi } from 'vitest';
import { mossAddDocsTool, mossDeleteDocsTool } from '../src/tools/docs.js';

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

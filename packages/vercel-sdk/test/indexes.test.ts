import { describe, it, expect, vi } from 'vitest';
import { mossCreateIndexTool, mossListIndexesTool, mossLoadIndexTool } from '../src/tools/indexes.js';

function createMockClient() {
  return {
    query: vi.fn(),
    createIndex: vi.fn().mockResolvedValue({ indexName: 'new-index', status: 'created' }),
    getIndex: vi.fn(),
    listIndexes: vi.fn().mockResolvedValue({ indexes: [{ name: 'idx-1' }, { name: 'idx-2' }] }),
    deleteIndex: vi.fn(),
    addDocs: vi.fn(),
    deleteDocs: vi.fn(),
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

describe('mossCreateIndexTool', () => {
  it('creates a tool with correct description', () => {
    const client = createMockClient();
    const tool = mossCreateIndexTool({ client });

    expect(tool.description).toContain('Create a new MOSS');
    expect(tool.inputSchema).toBeDefined();
  });

  it('executes with provided input', async () => {
    const client = createMockClient();
    const tool = mossCreateIndexTool({ client });

    const docs = [{ id: 'doc1', text: 'hello world' }];
    await tool.execute!(
      { indexName: 'new-index', docs, modelId: 'moss-minilm' },
      toolCallContext,
    );

    expect(client.createIndex).toHaveBeenCalledWith('new-index', docs, {
      modelId: 'moss-minilm',
    });
  });

  it('sets needsApproval to true', () => {
    const client = createMockClient();
    const tool = mossCreateIndexTool({ client });

    expect(tool.needsApproval).toBe(true);
  });

  it('accepts a custom description', () => {
    const client = createMockClient();
    const tool = mossCreateIndexTool({ client, description: 'Custom create' });

    expect(tool.description).toBe('Custom create');
  });
});

describe('mossListIndexesTool', () => {
  it('creates a tool with correct description', () => {
    const client = createMockClient();
    const tool = mossListIndexesTool({ client });

    expect(tool.description).toContain('List all');
    expect(tool.inputSchema).toBeDefined();
  });

  it('executes and returns indexes', async () => {
    const client = createMockClient();
    const tool = mossListIndexesTool({ client });

    const result = await tool.execute!({}, toolCallContext);

    expect(client.listIndexes).toHaveBeenCalled();
    expect(result).toHaveProperty('indexes');
  });

  it('accepts a custom description', () => {
    const client = createMockClient();
    const tool = mossListIndexesTool({ client, description: 'Custom list' });

    expect(tool.description).toBe('Custom list');
  });
});

describe('mossLoadIndexTool', () => {
  it('creates a tool with correct description', () => {
    const client = createMockClient();
    const tool = mossLoadIndexTool({ client });

    expect(tool.description).toContain('Load a MOSS index');
    expect(tool.inputSchema).toBeDefined();
  });

  it('executes with indexName from input', async () => {
    const client = createMockClient();
    client.loadIndex.mockResolvedValue('my-index');
    const tool = mossLoadIndexTool({ client });

    const result = await tool.execute!(
      { indexName: 'my-index', autoRefresh: false },
      toolCallContext,
    );

    expect(client.loadIndex).toHaveBeenCalledWith('my-index', {});
    expect(result).toEqual({ indexName: 'my-index', status: 'loaded' });
  });

  it('uses bound indexName when provided', async () => {
    const client = createMockClient();
    client.loadIndex.mockResolvedValue('bound-index');
    const tool = mossLoadIndexTool({ client, indexName: 'bound-index' });

    const result = await tool.execute!(
      { autoRefresh: false },
      toolCallContext,
    );

    expect(client.loadIndex).toHaveBeenCalledWith('bound-index', {});
    expect(result).toEqual({ indexName: 'bound-index', status: 'loaded' });
  });

  it('passes autoRefresh and pollingIntervalInSeconds', async () => {
    const client = createMockClient();
    client.loadIndex.mockResolvedValue('my-index');
    const tool = mossLoadIndexTool({ client });

    await tool.execute!(
      { indexName: 'my-index', autoRefresh: true, pollingIntervalInSeconds: 120 },
      toolCallContext,
    );

    expect(client.loadIndex).toHaveBeenCalledWith('my-index', {
      autoRefresh: true,
      pollingIntervalInSeconds: 120,
    });
  });

  it('accepts a custom description', () => {
    const client = createMockClient();
    const tool = mossLoadIndexTool({ client, description: 'Custom load' });

    expect(tool.description).toBe('Custom load');
  });
});

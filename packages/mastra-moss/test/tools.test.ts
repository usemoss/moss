import { describe, expect, it, vi } from 'vitest';
import type { MossClient } from '@moss-dev/moss';

import { mossAddDocsTool, mossSearchTool } from '../src/tools.js';

type StandardSchema = {
  '~standard': {
    validate: (input: unknown) => Promise<{ value?: unknown; issues?: unknown[] }>;
  };
};

function fakeClient() {
  return {
    query: vi.fn(async () => ({
      docs: [
        {
          id: 'doc-1',
          text: 'Refunds are accepted within 30 days.',
          score: 0.93,
          metadata: { source: 'faq' },
        },
      ],
    })),
    addDocs: vi.fn(async () => ({ jobId: 'job-1', docCount: 2 })),
  } as unknown as MossClient & {
    query: ReturnType<typeof vi.fn>;
    addDocs: ReturnType<typeof vi.fn>;
  };
}

async function validateInput(tool: { inputSchema: unknown }, input: unknown) {
  return (tool.inputSchema as StandardSchema)['~standard'].validate(input);
}

describe('mossSearchTool', () => {
  it('uses a bound indexName and hides indexName from required input', async () => {
    const client = fakeClient();
    const tool = mossSearchTool({
      client,
      indexName: 'support-kb',
      topK: 7,
      alpha: 0.4,
    });

    await expect(validateInput(tool, { query: 'refund policy' })).resolves.toMatchObject({
      value: { query: 'refund policy' },
    });

    const result = await tool.execute?.({ query: 'refund policy' });

    expect(client.query).toHaveBeenCalledWith('support-kb', 'refund policy', {
      topK: 7,
      alpha: 0.4,
    });
    expect(result).toEqual([
      {
        text: 'Refunds are accepted within 30 days.',
        score: 0.93,
        metadata: { source: 'faq' },
      },
    ]);
  });

  it('requires indexName when no index is bound', async () => {
    const client = fakeClient();
    const tool = mossSearchTool({ client });

    const missingIndex = await validateInput(tool, { query: 'refund policy' });
    expect(missingIndex.issues).toBeDefined();

    await expect(
      validateInput(tool, { indexName: 'support-kb', query: 'refund policy' }),
    ).resolves.toMatchObject({
      value: { indexName: 'support-kb', query: 'refund policy' },
    });

    await tool.execute?.({ indexName: 'support-kb', query: 'refund policy' });

    expect(client.query).toHaveBeenCalledWith('support-kb', 'refund policy', {
      topK: 5,
      alpha: 0.8,
    });
  });
});

describe('mossAddDocsTool', () => {
  it('uses a bound indexName and calls addDocs with upsert', async () => {
    const client = fakeClient();
    const tool = mossAddDocsTool({ client, indexName: 'support-kb' });
    const docs = [
      { id: 'doc-1', text: 'New support fact.', metadata: { source: 'agent' } },
      { id: 'doc-2', text: 'Another support fact.' },
    ];

    await expect(validateInput(tool, { docs })).resolves.toMatchObject({ value: { docs } });

    const result = await tool.execute?.({ docs });

    expect(client.addDocs).toHaveBeenCalledWith('support-kb', docs, { upsert: true });
    expect(result).toEqual({ jobId: 'job-1', docCount: 2 });
  });

  it('requires indexName for addDocs when no index is bound', async () => {
    const client = fakeClient();
    const tool = mossAddDocsTool({ client });
    const docs = [{ id: 'doc-1', text: 'New support fact.' }];

    const missingIndex = await validateInput(tool, { docs });
    expect(missingIndex.issues).toBeDefined();

    await expect(validateInput(tool, { indexName: 'support-kb', docs })).resolves.toMatchObject({
      value: { indexName: 'support-kb', docs },
    });

    await tool.execute?.({ indexName: 'support-kb', docs });

    expect(client.addDocs).toHaveBeenCalledWith('support-kb', docs, { upsert: true });
  });
});


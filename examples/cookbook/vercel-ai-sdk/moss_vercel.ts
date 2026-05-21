import { MossClient } from '@moss-dev/moss';
import { mossSearchTool, mossLoadIndexTool } from '@moss-tools/vercel-sdk';

export async function createMossTools(client: MossClient, indexName: string) {
  await client.loadIndex(indexName);
  return {
    search: mossSearchTool({ client, indexName }),
    loadIndex: mossLoadIndexTool({ client, indexName }),
  };
}

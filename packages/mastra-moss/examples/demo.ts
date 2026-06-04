/**
 * Demo: Moss semantic search with a Mastra agent.
 *
 * Setup:
 *   npm install @mastra/core @moss-dev/moss @moss-tools/mastra dotenv
 *
 * Run:
 *   npx tsx examples/demo.ts
 */

import { Agent } from '@mastra/core/agent';
import { MossClient } from '@moss-dev/moss';
import { config } from 'dotenv';
import { mossSearchTool } from '../src/index.js';

config();

const projectId = process.env.MOSS_PROJECT_ID;
const projectKey = process.env.MOSS_PROJECT_KEY;
const indexName = process.env.MOSS_INDEX_NAME;

if (!projectId || !projectKey || !indexName) {
  console.error('Missing MOSS_PROJECT_ID, MOSS_PROJECT_KEY, or MOSS_INDEX_NAME');
  process.exit(1);
}

const client = new MossClient(projectId, projectKey);

// Load the index once at startup for sub-10ms queries
await client.loadIndex(indexName);

const agent = new Agent({
  id: 'support-agent',
  name: 'Knowledge Support Copilot',
  instructions:
    'You are a helpful support assistant with access to a knowledge base. ' +
    'Use the moss_search tool to find relevant information before answering questions. ' +
    'Always cite the retrieved content in your response.',
  model: 'openai/gpt-4.1-mini',
  tools: {
    search: mossSearchTool({ client, indexName }),
  },
});

const response = await agent.generate('What is your refund policy?');
console.log(response.text);

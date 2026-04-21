/**
 * Moss + Mastra Integration Cookbook Example
 * 
 * This example demonstrates how to wrap Moss semantic search into a Mastra agent tool,
 * and provide it to a Mastra Language Model agent.
 */

import { Agent } from '@mastra/core/agent';
import { createTool } from '@mastra/core/tools';
import { MossClient } from '@moss-dev/moss';
import { z } from 'zod';
import { config } from 'dotenv';
import * as path from 'path';

// Load environment variables from parent .env if missing
config({ path: path.join(__dirname, '../../../.env') });
config();

async function runExample() {
  const projectId = process.env.MOSS_PROJECT_ID;
  const projectKey = process.env.MOSS_PROJECT_KEY;
  const indexName = process.env.MOSS_INDEX_NAME;
  const openaiApiKey = process.env.OPENAI_API_KEY;

  if (!projectId || !projectKey || !indexName || !openaiApiKey) {
    console.error('Error: Missing required environment variables!');
    console.error('Please set MOSS_PROJECT_ID, MOSS_PROJECT_KEY, MOSS_INDEX_NAME, and OPENAI_API_KEY');
    return;
  }

  // 1. Create a Mastra Tool for Moss Semantic Search
  const mossSearchTool = createTool({
    id: 'moss-search',
    description: 'Search for information in the company knowledge base or FAQ using Moss semantic search. Requires a query string.',
    inputSchema: z.object({
      query: z.string().describe('The semantic search query'),
    }),
    execute: async ({ query }) => {
      console.log(`[moss-search-tool] Searching for: "${query}"...`);
      const client = new MossClient(projectId, projectKey);
      
      // Load the index before querying
      await client.loadIndex(indexName);
      
      // Perform fast semantic search (sub-10 ms!)
      const results = await client.query(indexName, query, { topK: 3 });
      
      console.log(`[moss-search-tool] Found ${results.docs.length} results in ${results.timeTakenInMs}ms.`);
      
      return {
        results: results.docs.map(doc => ({
          content: doc.text,
          score: doc.score,
        })),
        timeTakenInMs: results.timeTakenInMs,
      };
    },
  });

  // 1.1 Create a Mastra Tool for Indexing into Moss
  const mossIndexTool = createTool({
    id: 'moss-index',
    description: 'Index new information into the company knowledge base using Moss. Requires text to index.',
    inputSchema: z.object({
      text: z.string().describe('The information text to index'),
      id: z.string().optional().describe('Optional unique identifier for the document'),
    }),
    execute: async ({ text, id }) => {
      console.log(`[moss-index-tool] Indexing snippet: "${text.substring(0, 50)}..."`);
      const client = new MossClient(projectId, projectKey);
      
      const docId = id || `doc_${Date.now()}`;
      
      await client.addDocs(indexName, [
        { id: docId, text }
      ], { upsert: true });
      
      console.log(`[moss-index-tool] Successfully indexed document ID: ${docId}`);
      
      return {
        success: true,
        docId,
      };
    },
  });

  // 2. Wrap into a Mastra Agent
  const supportAgent = new Agent({
    id: 'support-agent',
    name: 'Knowledge Support Copilot',
    instructions: 'You are an exceptional support assistant. Call the `moss-search` tool to fetch context from the knowledge base to answer questions. If you learn something new or important that should be remembered, use the `moss-index` tool to store it. Cite retrieved details.',
    model: 'openai/gpt-4.1-mini', 
    tools: { mossSearchTool, mossIndexTool },
  });

  // 3. Execution
  console.log('\n--- Scenario 1: Retrieval ---');
  const userPrompt1 = 'How long does a refund take and how can I track my order?';
  console.log(`User Prompt: "${userPrompt1}"`);
  const response1 = await supportAgent.generate(userPrompt1);
  console.log('\nFinal Agent Response:', response1.text);

  console.log('\n--- Scenario 2: Learning and Indexing ---');
  const userPrompt2 = 'Please note that for premium members, refunds are processed instantly. Please remember this for future support.';
  console.log(`User Prompt: "${userPrompt2}"`);
  const response2 = await supportAgent.generate(userPrompt2);
  console.log('\nFinal Agent Response:', response2.text);
}

if (require.main === module) {
  runExample().catch(console.error);
}

import 'dotenv/config';
import { MossClient } from '@moss-dev/moss';
import { mossSearchTool } from '@moss-tools/vercel-sdk';
import { generateText, streamText } from 'ai';
import { openai } from '@ai-sdk/openai';
import { requireEnv } from './utils.js';

async function main() {
  const client = new MossClient(
    requireEnv('MOSS_PROJECT_ID'),
    requireEnv('MOSS_PROJECT_KEY'),
  );

  const indexName = requireEnv('MOSS_INDEX_NAME');
  const model = process.env.OPENAI_MODEL ?? 'gpt-4o-mini';

  // Run "npm run seed" first to create this index with sample documents,
  // or point MOSS_INDEX_NAME at an index you already have.
  const useGenerate = process.env.GENERATE === 'true';

  // Prebind the search tool to a single index, so the LLM only needs to
  // supply a query, not an index name.
  const tools = {
    search: mossSearchTool({ client, indexName }),
  };

const systemPrompt =
  'You are a helpful assistant. Always use the search tool to find relevant ' +
  'context before answering, and cite what you find in your response.';

const question = process.argv[2] ?? 'What does this knowledge base cover?';
  console.log(`Q: ${question}\n`);

if (useGenerate) {
  const { text } = await generateText({
    model: openai(model),
    tools,
    system: systemPrompt,
    prompt: question,
    maxSteps: 3,
  });

  console.log(`A: ${text}`);
} else {
  // Default: stream the answer token-by-token as it's generated, retrieving
  // grounded context from Moss along the way.
  const result = streamText({
    model: openai(model),
    tools,
    system: systemPrompt,
    prompt: question,
    maxSteps: 3,
  });

  process.stdout.write('A: ');
  for await (const chunk of result.textStream) {
    process.stdout.write(chunk);
  }
  console.log();
}
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

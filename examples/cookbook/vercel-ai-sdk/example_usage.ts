import { MossClient } from '@moss-dev/moss';
import { generateText, streamText } from 'ai';
import { openai } from '@ai-sdk/openai';
import { config } from 'dotenv';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createMossTools } from './moss_vercel.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
config({ path: path.join(__dirname, '../../../.env') });
config();

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`Missing required environment variable: ${name}`);
  return value;
}

async function run() {
  const client = new MossClient(
    requireEnv('MOSS_PROJECT_ID'),
    requireEnv('MOSS_PROJECT_KEY'),
  );
  const indexName = requireEnv('MOSS_INDEX_NAME');
  const model = process.env.OPENAI_MODEL ?? 'gpt-4o-mini';

  console.log(`Loading index "${indexName}" into memory for fast local queries...`);
  const tools = await createMossTools(client, indexName);
  console.log('Index loaded.\n');
  const systemPrompt =
    'You are a helpful customer support assistant. Use the search tool to find ' +
    'relevant information before answering. Always cite the retrieved context in your response.';

  // --- Scenario 1: generateText (single-turn Q&A) ---
  console.log('--- Scenario 1: generateText ---');
  const question = 'How long does a refund take and what is the return policy?';
  console.log(`User: ${question}`);

  const { text, steps } = await generateText({
    model: openai(model),
    tools,
    maxSteps: 3,
    system: systemPrompt,
    prompt: question,
  });

  console.log(`\nAssistant: ${text}`);
  console.log(`Tool calls made: ${steps.flatMap((s) => s.toolCalls).length}\n`);

  // --- Scenario 2: streamText (streaming response) ---
  console.log('--- Scenario 2: streamText ---');
  const streamQuestion = 'What payment methods do you accept and how do I cancel my subscription?';
  console.log(`User: ${streamQuestion}`);
  process.stdout.write('\nAssistant: ');

  const stream = streamText({
    model: openai(model),
    tools,
    maxSteps: 3,
    system: systemPrompt,
    prompt: streamQuestion,
  });

  for await (const chunk of stream.textStream) {
    process.stdout.write(chunk);
  }
  console.log('\n');
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});

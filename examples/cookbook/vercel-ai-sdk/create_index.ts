import 'dotenv/config';
import { MossClient } from '@moss-dev/moss';
import { sampleDocs } from './seed_data.js';

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

async function seed() {
  const client = new MossClient(
    requireEnv('MOSS_PROJECT_ID'),
    requireEnv('MOSS_PROJECT_KEY'),
  );
  const indexName = requireEnv('MOSS_INDEX_NAME');

  const deleted = await client.deleteIndex(indexName);
  if (deleted) {
    console.log(`Deleted existing index "${indexName}".`);
  }

  console.log(
    `Creating index "${indexName}" with ${sampleDocs.length} sample documents...`,
  );
  await client.createIndex(indexName, sampleDocs);
  console.log('Done! You can now run "npm start" to query this index.');
}

seed().catch((err) => {
  console.error(err);
  process.exit(1);
});

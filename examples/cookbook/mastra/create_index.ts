import { MossClient } from '@moss-dev/moss';
import { sampleDocs } from './seed_data';
import { config } from 'dotenv';
import * as path from 'path';

config({ path: path.join(__dirname, '../../../.env') });
config();

async function createIndex() {
  const projectId = process.env.MOSS_PROJECT_ID;
  const projectKey = process.env.MOSS_PROJECT_KEY;
  const indexName = process.env.MOSS_INDEX_NAME;

  if (!projectId || !projectKey || !indexName) {
    console.error('Error: Missing MOSS_PROJECT_ID, MOSS_PROJECT_KEY, or MOSS_INDEX_NAME');
    process.exit(1);
  }

  const client = new MossClient(projectId, projectKey);

  const deleted = await client.deleteIndex(indexName);
  if (deleted) {
    console.log(`Deleted existing index "${indexName}".`);
  } else {
    console.log(`Index "${indexName}" did not exist, skipping delete.`);
  }

  console.log(`Creating index "${indexName}" with ${sampleDocs.length} documents...`);
  await client.createIndex(indexName, sampleDocs);
  console.log('Index created successfully!');
}

createIndex().catch(err => {
  console.error(err);
  process.exit(1);
});

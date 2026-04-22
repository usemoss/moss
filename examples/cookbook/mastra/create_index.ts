import { MossClient } from '@moss-dev/moss';
import { sampleDocs } from './seed_data';
import { config } from 'dotenv';
import * as path from 'path';

config({ path: path.join(__dirname, '../../../../.env') });
config();

async function seed() {
  const projectId = process.env.MOSS_PROJECT_ID;
  const projectKey = process.env.MOSS_PROJECT_KEY;
  const indexName = process.env.MOSS_INDEX_NAME;

  if (!projectId || !projectKey || !indexName) {
    console.error('Error: Missing MOSS_PROJECT_ID, MOSS_PROJECT_KEY, or MOSS_INDEX_NAME');
    process.exit(1);
  }

  console.log(`Seeding index "${indexName}" with ${sampleDocs.length} documents...`);
  
  const client = new MossClient(projectId, projectKey);

  try {
    // Create the index with the sample documents
    await client.createIndex(indexName, sampleDocs);
    console.log('Seeding completed successfully!');
  } catch (error) {
    console.error('Error seeding index:', error);
    process.exit(1);
  }
}

seed();

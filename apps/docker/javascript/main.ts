/**
 * Moss JS SDK - Docker Example
 *
 * Demonstrates how to use the Moss JS SDK inside a container
 * (as you would in AWS ECS, Kubernetes, etc.).
 *
 * Env vars (set via docker-compose or your container runtime):
 *   MOSS_PROJECT_ID   - Your Moss project ID
 *   MOSS_PROJECT_KEY  - Your Moss project key
 *   MOSS_INDEX_NAME   - Name of the index to query
 */

import { MossClient } from "@inferedge/moss";
import { config } from "dotenv";

config();

async function main(): Promise<void> {
  const projectId = process.env.MOSS_PROJECT_ID;
  const projectKey = process.env.MOSS_PROJECT_KEY;
  const indexName = process.env.MOSS_INDEX_NAME;

  if (!projectId || !projectKey || !indexName) {
    console.error(
      "Error: MOSS_PROJECT_ID, MOSS_PROJECT_KEY, and MOSS_INDEX_NAME must be set."
    );
    process.exit(1);
  }

  const client = new MossClient(projectId, projectKey);

  console.log(`Loading index '${indexName}'...`);
  await client.loadIndex(indexName);
  console.log("Index loaded.");

  const query = "what is your return policy";
  console.log(`\nQuerying: '${query}'`);
  const results = await client.query(indexName, query, { topK: 3 });

  console.log(
    `Found ${results.docs.length} results in ${results.timeTakenInMs}ms\n`
  );
  results.docs.forEach((result) => {
    console.log(`  [${result.id}] score=${result.score.toFixed(3)}`);
    console.log(`  ${result.text}\n`);
  });
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

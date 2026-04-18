/**
 * Loads a tiered Moss index and performs a sample search query.
 *
 * Set MOSS_INDEX_TIER in .env to choose the tier (default: 1k).
 */

import { MossClient } from "@inferedge/moss";
import * as path from "path";
import { config } from "dotenv";

config({ path: path.resolve(__dirname, "../.env") });

const TOP_K = 5;

const SAMPLE_QUERIES: readonly string[] = [
  "a dog catching a frisbee in mid-air",
  "people riding bikes down a city street",
  "a cat sitting on a laptop keyboard",
  "a large pizza on a wooden table",
  "surfers riding waves at the beach",
];

async function loadAndQuerySample(): Promise<void> {
  console.log("Moss SDK - Search Query Sample");

  const projectId = process.env.MOSS_PROJECT_ID;
  const projectKey = process.env.MOSS_PROJECT_KEY;
  const baseIndexName = process.env.MOSS_INDEX_NAME;
  const tier = process.env.MOSS_INDEX_TIER || "1k";

  if (!projectId || !projectKey || !baseIndexName) {
    console.error("Error: Missing required environment variables!");
    console.error(
      "Please set MOSS_PROJECT_ID, MOSS_PROJECT_KEY, and MOSS_INDEX_NAME in .env file"
    );
    return;
  }

  const indexName = `${baseIndexName}-${tier}`;
  console.log(`Using index: ${indexName} (tier: ${tier})`);

  const client = new MossClient(projectId, projectKey);

  try {
    console.log("\nLoading index...");
    await client.loadIndex(indexName);
    console.log("Index loaded successfully");

    for (const query of SAMPLE_QUERIES) {
      console.log(`\nPerforming search for: "${query}"`);
      const searchResults = await client.query(indexName, query, { topK: TOP_K });

      console.log(`Time taken: ${searchResults.timeTakenInMs} ms`);
      console.log(`Results: ${searchResults.docs.length}`);
      console.log(searchResults.docs);
    }

    console.log("\nAll queries completed successfully!");
  } catch (error) {
    console.error(`Error: ${error}`);
  }
}

if (require.main === module) {
  loadAndQuerySample().catch(console.error);
}

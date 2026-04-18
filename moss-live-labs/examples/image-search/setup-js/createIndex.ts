/**
 * Creates a Moss index from a tiered COCO dataset JSON file.
 *
 * Set MOSS_INDEX_TIER in .env to choose the tier (1k, 10k, 50k, 100k).
 * The index name will be "${MOSS_INDEX_NAME}-${tier}".
 */

import { MossClient, DocumentInfo } from "@inferedge/moss";
import * as fs from "fs";
import * as path from "path";
import { config } from "dotenv";

config({ path: path.resolve(__dirname, "../.env") });

const VALID_TIERS = ["1k", "10k", "50k", "100k"] as const;
type Tier = (typeof VALID_TIERS)[number];

function getDataFilePath(tier: Tier): string {
  return path.resolve(__dirname, `../coco-data-${tier}.json`);
}

function getIndexName(baseName: string, tier: Tier): string {
  return `${baseName}-${tier}`;
}

async function createIndexForTier(tier: Tier): Promise<void> {
  const projectId = process.env.MOSS_PROJECT_ID;
  const projectKey = process.env.MOSS_PROJECT_KEY;
  const baseIndexName = process.env.MOSS_INDEX_NAME;

  if (!projectId || !projectKey || !baseIndexName) {
    console.error("Error: Missing environment variables!");
    console.error(
      "Please set MOSS_PROJECT_ID, MOSS_PROJECT_KEY, and MOSS_INDEX_NAME in .env file"
    );
    return;
  }

  const dataFile = getDataFilePath(tier);
  if (!fs.existsSync(dataFile)) {
    console.error(`Error: Data file not found: ${dataFile}`);
    console.error("Run downloadCoco.ts first to generate the data files.");
    return;
  }

  const raw = fs.readFileSync(dataFile, "utf-8");
  const docs = JSON.parse(raw) as DocumentInfo[];
  const indexName = getIndexName(baseIndexName, tier);

  console.log(`Loaded ${docs.length} documents from coco-data-${tier}.json`);

  const client = new MossClient(projectId, projectKey);

  // Check if index already exists
  try {
    const existing = await client.getIndex(indexName);
    console.log(
      `Index "${indexName}" already exists with ${existing.docCount} documents. Skipping creation.`
    );
    return;
  } catch {
    // Index doesn't exist, proceed with creation
  }

  await client.createIndex(indexName, docs, { modelId: "moss-minilm" });
  console.log(
    `Index "${indexName}" created successfully with ${docs.length} documents.`
  );
}

// Run directly
const tier = (process.env.MOSS_INDEX_TIER || "1k") as Tier;
if (!VALID_TIERS.includes(tier)) {
  console.error(`Invalid tier: ${tier}. Valid tiers: ${VALID_TIERS.join(", ")}`);
  process.exit(1);
}

createIndexForTier(tier).catch(console.error);

export { createIndexForTier, VALID_TIERS };

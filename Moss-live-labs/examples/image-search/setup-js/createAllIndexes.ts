/**
 * Creates Moss indexes for all four COCO tiers sequentially.
 *
 * Requires MOSS_PROJECT_ID, MOSS_PROJECT_KEY, and MOSS_INDEX_NAME in .env.
 * Data files (coco-data-*.json) must exist — run downloadCoco.ts first.
 */

import * as path from "path";
import { createIndexForTier, VALID_TIERS } from "./createIndex";
import { config } from "dotenv";

config({ path: path.resolve(__dirname, "../.env") });

async function createAllIndexes(): Promise<void> {
  console.log("Creating indexes for all tiers...\n");

  for (const tier of VALID_TIERS) {
    console.log(`\n--- Tier: ${tier} ---`);
    try {
      await createIndexForTier(tier);
    } catch (error) {
      console.error(`Failed to create index for tier ${tier}:`, error);
    }
  }

  console.log("\nAll indexes created.");
}

createAllIndexes().catch(console.error);

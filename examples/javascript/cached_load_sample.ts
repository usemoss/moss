/**
 * Moss SDK - Cached Index Loading Sample
 *
 * Demonstrates two `loadIndex` configurations:
 *
 * 1. Basic cache — the index binary is downloaded once and saved under `cachePath`.
 *    Subsequent loads read from disk instead of the network (instant).
 *
 * 2. Cache + auto-refresh — same disk cache, but the SDK also polls the cloud
 *    every `pollingIntervalInSeconds` seconds. When a newer version is detected
 *    the index is hot-swapped in memory and the cache is refreshed on disk,
 *    all without interrupting in-flight queries.
 *
 * Required Environment Variables:
 * - MOSS_PROJECT_ID: Your Moss project ID
 * - MOSS_PROJECT_KEY: Your Moss project key
 * - MOSS_INDEX_NAME: Name of an existing index to query
 *
 * @example
 * ```bash
 * npm run cached-load
 * ```
 */

import { MossClient } from "@moss-dev/moss";
import { performance } from "node:perf_hooks";
import { config } from "dotenv";

config();

const CACHE_DIR = "./.moss-cache";

async function cachedLoadSample(): Promise<void> {
  console.log("Moss SDK - Cached Index Loading Sample");
  console.log("=".repeat(45));

  const projectId = process.env.MOSS_PROJECT_ID;
  const projectKey = process.env.MOSS_PROJECT_KEY;
  const indexName = process.env.MOSS_INDEX_NAME;

  if (!projectId || !projectKey || !indexName) {
    console.error(
      "Error: Please set MOSS_PROJECT_ID, MOSS_PROJECT_KEY, and MOSS_INDEX_NAME in .env"
    );
    return;
  }

  const client = new MossClient(projectId, projectKey);

  // ── 1. Basic cache load ────────────────────────────────────────────────────
  // First run: downloads from cloud and writes to CACHE_DIR.
  // Subsequent runs: reads from disk — no network call, loads in <10ms.
  console.log(`\nLoading index '${indexName}' with disk cache (${CACHE_DIR})...`);
  let start = performance.now();
  await client.loadIndex(indexName, { cachePath: CACHE_DIR });
  console.log(`Loaded in ${(performance.now() - start).toFixed(0)}ms`);

  const queries = [
    "how to return damaged item",
    "return shipping label process",
    "refund processing time and policy",
  ];

  console.log("\nRunning queries against the cached index...");
  for (const query of queries) {
    const results = await client.query(indexName, query, { topK: 3 });
    console.log(
      `\n  "${query}" -> ${results.docs.length} results (${results.timeTakenInMs}ms)`
    );
    results.docs.forEach((doc, i) => {
      const preview =
        doc.text.length > 80 ? doc.text.substring(0, 80) + "..." : doc.text;
      console.log(`    ${i + 1}. [${doc.id}] score=${doc.score.toFixed(3)}`);
      console.log(`       ${preview}`);
    });
  }

  // ── 2. Cache + auto-refresh ────────────────────────────────────────────────
  // The SDK polls the cloud every `pollingIntervalInSeconds` seconds.
  // When a newer index version is found it is hot-swapped into memory and
  // persisted to the cache — no manual reload required.
  //
  // Use this in long-running servers or background workers where the index
  // content updates over time (e.g. a live knowledge base).
  console.log("\nReloading with auto-refresh enabled (polls every 60 s)...");
  start = performance.now();
  await client.loadIndex(indexName, {
    cachePath: CACHE_DIR,
    autoRefresh: true,
    pollingIntervalInSeconds: 60,
  });
  console.log(`Reloaded in ${(performance.now() - start).toFixed(0)}ms`);
  console.log("Index will auto-refresh in the background every 60 seconds.");

  // Queries continue to work normally while auto-refresh runs in the background.
  const result = await client.query(indexName, "refund policy", { topK: 2 });
  console.log(
    `\nQuery after auto-refresh setup: ${result.docs.length} results (${result.timeTakenInMs}ms)`
  );

  // Stop auto-refresh by reloading without the option.
  await client.loadIndex(indexName, { cachePath: CACHE_DIR });
  console.log("Auto-refresh stopped (reloaded without autoRefresh option).");

  console.log("\nDone! Run again to see the faster cached load time. (Ctrl+C to exit)");
}

export { cachedLoadSample };

if (require.main === module) {
  cachedLoadSample().catch(console.error);
}

/**
 * Moss Browser SDK - Load & Query Sample
 *
 * Loads an existing index into browser memory and runs semantic searches.
 *
 * Requires a Moss project with at least one published index.
 */

import { MossClient } from "@moss-dev/moss-web";

const $ = (id: string) => document.getElementById(id) as HTMLInputElement;
const logEl = $("log");
const log = (msg: string) => {
  logEl.textContent += msg + "\n";
};
const clear = () => {
  logEl.textContent = "";
};

$("run").addEventListener("click", run);

async function run() {
  clear();

  const projectId = $("projectId").value.trim();
  const projectKey = $("projectKey").value.trim();
  const indexName = $("indexName").value.trim();

  if (!projectId || !projectKey || !indexName) {
    log("Please fill in all fields.");
    return;
  }

  let client: MossClient | null = null;

  try {
    log("Initializing MossClient...");
    client = new MossClient(projectId, projectKey);

    log(`Loading index "${indexName}"...`);
    await client.loadIndex(indexName);
    log("Index loaded into browser memory.\n");

    const queries = [
      "how to return damaged item",
      "return shipping label process",
      "refund processing time and policy",
    ];

    for (let i = 0; i < queries.length; i++) {
      const q = queries[i];
      log(`Query ${i + 1}: "${q}"`);

      const results = await client.query(indexName, q, { topK: 3 });
      log(`  ${results.docs.length} results in ${results.timeTakenMs ?? "?"}ms`);

      for (const doc of results.docs) {
        const preview =
          doc.text.length > 100 ? doc.text.slice(0, 100) + "..." : doc.text;
        log(`  ${doc.score.toFixed(3)}  [${doc.id}] ${preview}`);
      }
      log("");
    }

    log("Done.");
  } catch (err) {
    log(`Error: ${err instanceof Error ? err.message : err}`);
  } finally {
    client?.dispose();
  }
}

/**
 * Moss SDK - Session Sample
 *
 * A `SessionIndex` is a local, in-process index: documents are embedded and
 * queried entirely in memory with no cloud round-trip. At the end of a session
 * call `pushIndex()` to persist it to the cloud so another agent or device can
 * resume it via `loadIndex()`.
 *
 * Typical use-cases:
 *  - Indexing a live conversation turn-by-turn as it happens
 *  - Ephemeral per-user or per-request search spaces
 *  - Offline-first mobile apps that sync on demand
 *
 * Required Environment Variables:
 * - MOSS_PROJECT_ID: Your Moss project ID
 * - MOSS_PROJECT_KEY: Your Moss project key
 * - MOSS_INDEX_NAME: Name for the session index. Defaults to "session-demo".
 *
 * @example
 * ```bash
 * npm run session
 * ```
 */

import { MossClient, DocumentInfo } from "@moss-dev/moss";
import { config } from "dotenv";

config();

async function sessionSample(): Promise<void> {
  console.log("Moss SDK - Session Sample");
  console.log("=".repeat(40));

  const projectId = process.env.MOSS_PROJECT_ID;
  const projectKey = process.env.MOSS_PROJECT_KEY;
  const indexName = process.env.MOSS_INDEX_NAME ?? "session-demo";

  if (!projectId || !projectKey) {
    console.error("Error: Please set MOSS_PROJECT_ID and MOSS_PROJECT_KEY in .env");
    return;
  }

  const client = new MossClient(projectId, projectKey);

  try {
    // Open a session. If a cloud index with this name already exists it is
    // loaded into the session automatically; otherwise it starts empty.
    console.log(`\nOpening session '${indexName}'...`);
    const session = await client.session(indexName);
    console.log(`Session open (${session.docCount} pre-existing docs, model: ${session.modelId})`);

    // Add documents locally — embeddings are generated in Rust, no network call.
    console.log("\nAdding documents locally...");
    const turns: DocumentInfo[] = [
      { id: "turn-1", text: "Customer was charged twice for the March renewal." },
      { id: "turn-2", text: "Agent confirmed a refund for the duplicate charge." },
      { id: "turn-3", text: "Customer also asked to cancel auto-renew." },
    ];
    const { added, updated } = await session.addDocs(turns);
    console.log(`${added} added, ${updated} updated (${session.docCount} total in session)`);

    // Retrieve the documents we just added.
    console.log("\nRetrieving all session docs...");
    const docs = await session.getDocs();
    docs.forEach((doc) => {
      console.log(`  [${doc.id}] ${doc.text}`);
    });

    // Query the in-memory index — typically 1-10 ms with no network latency.
    console.log("\nQuerying the session...");
    const results = await session.query("what did the customer want refunded", { topK: 3 });
    console.log(`${results.docs.length} results:`);
    results.docs.forEach((doc) => {
      console.log(`  [${doc.id}] score=${doc.score.toFixed(3)}  ${doc.text}`);
    });

    // Push the session to the cloud so another process can resume it.
    console.log("\nPushing session to the cloud...");
    const pushed = await session.pushIndex();
    console.log(`Pushed ${pushed.docCount} docs (job ${pushed.jobId})`);

    console.log("\nDone! Another agent can now resume this session with: (Ctrl+C to exit)");
    console.log(`  const session = await client.session('${indexName}');`);
  } catch (error) {
    console.error(`Error: ${error}`);
  }
}

export { sessionSample };

if (require.main === module) {
  sessionSample().catch(console.error);
}

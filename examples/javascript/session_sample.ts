/**
 * Moss SDK Session Sample
 *
 * A SessionIndex is a local, in-process index you read and write in real time with no
 * cloud round trip, then push to the cloud so another agent or device can resume it.
 * This is how Moss indexes a live conversation (e.g. voice/chat transcript turns).
 *
 * Required Environment Variables:
 * - MOSS_PROJECT_ID: Your Moss project ID
 * - MOSS_PROJECT_KEY: Your Moss project key
 * - MOSS_INDEX_NAME: Name for the session index (created or resumed). Defaults to "session-demo".
 */

import { MossClient, DocumentInfo } from "@moss-dev/moss";
import { config } from "dotenv";

// Load environment variables
config();

/**
 * Open a session, index documents locally, query in-memory, then push to the cloud.
 */
async function sessionSample(): Promise<void> {
  console.log("Moss SDK - Session Sample");

  // Load configuration from environment variables
  const projectId = process.env.MOSS_PROJECT_ID;
  const projectKey = process.env.MOSS_PROJECT_KEY;
  const indexName = process.env.MOSS_INDEX_NAME ?? "session-demo";

  if (!projectId || !projectKey) {
    console.error("Error: Missing required environment variables!");
    console.error("Please set MOSS_PROJECT_ID and MOSS_PROJECT_KEY in .env file");
    return;
  }

  // Initialize Moss client
  const client = new MossClient(projectId, projectKey);

  try {
    // Open a session by name. If a cloud index with this name already exists it
    // auto-loads; otherwise the session starts empty. No cloud round trip on add/query.
    console.log(`\nOpening session '${indexName}'...`);
    const session = await client.session(indexName);
    console.log(`Session open (${session.docCount} existing docs)`);

    // Add documents as they arrive (e.g. transcript turns). Embedded locally.
    console.log(`\nAdding documents locally...`);
    const turns: DocumentInfo[] = [
      { id: "turn-1", text: "Customer was charged twice for the March renewal." },
      { id: "turn-2", text: "Agent confirmed a refund for the duplicate charge." },
      { id: "turn-3", text: "Customer also asked to cancel auto-renew." },
    ];
    const { added, updated } = await session.addDocs(turns);
    console.log(`${added} added, ${updated} updated (${session.docCount} total)`);

    // Query the in-memory session (~1-10 ms, no network).
    console.log(`\nQuerying the session...`);
    const results = await session.query("what did the customer want refunded", { topK: 3 });
    results.docs.forEach((doc) => {
      console.log(`  [${doc.id}] ${doc.score.toFixed(3)}  ${doc.text}`);
    });

    // Push the session to the cloud so another agent or device can resume it.
    console.log(`\nPushing session to the cloud...`);
    const pushed = await session.pushIndex();
    console.log(`Pushed ${pushed.docCount} docs (job ${pushed.jobId})`);

    console.log(`\nSample completed successfully!`);
  } catch (error) {
    console.error(`Error: ${error}`);
  }
}

// Run the example if this file is executed directly
if (require.main === module) {
  sessionSample().catch(console.error);
}

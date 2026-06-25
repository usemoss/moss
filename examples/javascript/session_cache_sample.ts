/**
 * Moss SDK Session Cache Sample
 *
 * A SessionIndex is local-first: documents are embedded and queried entirely
 * in-process, with no cloud round trip. `saveToDisk` / `loadFromDisk` let you
 * persist that in-memory index to the local filesystem and restore it later —
 * so a session can survive a process restart **without ever leaving the
 * device** (no `pushIndex`, nothing uploaded).
 *
 * This sample:
 *   1. Builds a session and saves it to local disk.
 *   2. Restores it into a fresh session (simulating a restart) and queries it.
 *
 * The client is constructed with a top-level `cachePath`, which is also where
 * the anonymous per-device telemetry id is persisted (`<cachePath>/.moss-device-id`).
 *
 * Requires `@moss-dev/moss` >= 1.2.1 (client-level `cachePath` option).
 *
 * Required Environment Variables:
 * - MOSS_PROJECT_ID: Your Moss project ID
 * - MOSS_PROJECT_KEY: Your Moss project key
 */

import { MossClient, DocumentInfo } from "@moss-dev/moss";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { config } from "dotenv";

// Load environment variables
config();

// Directory the session is cached to. saveToDisk writes the session under
// `<CACHE_DIR>/<sessionName>/`; the device-id file lives at `<CACHE_DIR>/.moss-device-id`.
const CACHE_DIR = "./.moss-session-cache";
const SESSION_NAME = "session-cache-demo";

async function sessionCacheSample(): Promise<void> {
  console.log("Moss SDK - Session Cache Sample");

  const projectId = process.env.MOSS_PROJECT_ID;
  const projectKey = process.env.MOSS_PROJECT_KEY;

  if (!projectId || !projectKey) {
    console.error("Error: set MOSS_PROJECT_ID and MOSS_PROJECT_KEY in .env");
    return;
  }

  // Top-level cachePath: one location, honored by every operation that emits
  // telemetry (loadIndex, session, …) for the per-device id.
  const client = new MossClient(projectId, projectKey, { cachePath: CACHE_DIR });

  try {
    // 1) Build a session and add documents locally (embedded on-device).
    console.log(`\nBuilding session '${SESSION_NAME}'...`);
    const session = await client.session(SESSION_NAME);
    const turns: DocumentInfo[] = [
      { id: "turn-1", text: "Customer was charged twice for the March renewal." },
      { id: "turn-2", text: "Agent confirmed a refund for the duplicate charge." },
      { id: "turn-3", text: "Customer also asked to cancel auto-renew." },
    ];
    await session.addDocs(turns);
    console.log(`Added ${session.docCount} docs (in memory)`);

    // 2) Persist the session to local disk — no cloud round trip.
    await session.saveToDisk(CACHE_DIR);
    console.log(`Saved session to ${join(CACHE_DIR, SESSION_NAME)}/ (local only)`);

    // 3) Simulate a restart: open a fresh, empty session and restore from disk.
    console.log(`\nRestoring into a fresh session (simulating a restart)...`);
    const restored = await client.session(SESSION_NAME);
    console.log(`Fresh session docs before restore: ${restored.docCount}`);
    const loaded = await restored.loadFromDisk(CACHE_DIR);
    console.log(`Restored ${loaded} docs from disk (${restored.docCount} total)`);

    // 4) Query the restored session — same data, still entirely local.
    console.log(`\nQuerying the restored session...`);
    const results = await restored.query("what did the customer want refunded", {
      topK: 3,
    });
    results.docs.forEach((doc) => {
      console.log(`  [${doc.id}] ${doc.score.toFixed(3)}  ${doc.text}`);
    });

    // The anonymous per-device id persisted under the client cachePath.
    const deviceIdFile = join(CACHE_DIR, ".moss-device-id");
    if (existsSync(deviceIdFile)) {
      console.log(`\nDevice id (anonymous): ${readFileSync(deviceIdFile, "utf8").trim()}`);
    }

    console.log(`\nDone — the documents never left the device (no pushIndex).`);
  } catch (error) {
    console.error(`Error: ${error}`);
  }
}

// Run the example if this file is executed directly
if (require.main === module) {
  sessionCacheSample().catch(console.error);
}

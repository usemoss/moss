import { readStdin, writeOutput } from "../lib/stdin.js";
import { loadSettings } from "../lib/settings.js";
import { loadState, saveState } from "../lib/state.js";
import { extractNewMessages } from "../lib/transcript.js";
import { cloudAddDocs } from "../lib/moss-rest.js";

const pass = () => writeOutput({ continue: true });

async function main() {
  const input = await readStdin();
  const settings = loadSettings();

  if (!settings || !settings.indexName) {
    pass();
    return;
  }

  const transcriptPath = input.transcript_path;
  if (!transcriptPath) {
    pass();
    return;
  }

  const sessionId = input.session_id || "default";
  const state = loadState(sessionId);

  // Extract only new messages since last capture
  const result = extractNewMessages(transcriptPath, state.lastUuid || null);
  if (!result) {
    pass();
    return;
  }

  // Format messages as Moss documents
  const docs = result.messages.map((msg, i) => ({
    id: `session-${sessionId}-${(state.lastUuid || "0").slice(0, 8)}-${i}`,
    text: `[${msg.role}] ${msg.content}`,
    metadata: {
      sessionId,
      role: msg.role,
      source: "conversation",
      capturedAt: new Date().toISOString(),
    },
  }));

  // Upload to Moss (best-effort, don't block on failure)
  try {
    await cloudAddDocs({
      projectId: settings.projectId,
      projectKey: settings.projectKey,
      indexName: settings.indexName,
      docs,
    });
  } catch {
    // Silent failure — conversation capture should never block
  }

  // Update cursor so next capture starts after these messages
  state.lastUuid = result.lastUuid;
  saveState(sessionId, state);

  pass();
}

main().catch(() => {
  pass();
});

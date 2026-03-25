import { readStdin, writeOutput } from "../lib/stdin.js";
import { loadSettings } from "../lib/settings.js";
import { loadState, saveState, dedup } from "../lib/state.js";
import { shouldTrigger } from "../lib/trigger.js";
import { cloudQuery } from "../lib/moss-rest.js";

const pass = () => writeOutput({ continue: true });

async function main() {
  const input = await readStdin();
  const settings = loadSettings();

  // No creds, no indexName, or auto-search disabled
  if (!settings || !settings.indexName || !settings.autoSearch) {
    pass();
    return;
  }

  const prompt = (input.prompt || "").trim();

  // Heuristic: only fire on knowledge-seeking prompts
  if (!shouldTrigger(prompt)) {
    pass();
    return;
  }

  // Query Moss cloud directly
  const result = await cloudQuery({
    projectId: settings.projectId,
    projectKey: settings.projectKey,
    indexName: settings.indexName,
    query: prompt,
    topK: settings.topK,
  });

  // Filter by score threshold
  const docs = (result.docs || []).filter(
    (d) => d.score >= settings.scoreThreshold
  );

  if (docs.length === 0) {
    pass();
    return;
  }

  // Bounded dedup
  const sessionId = input.session_id || "default";
  const state = loadState(sessionId);
  const freshIds = dedup(
    state,
    docs.map((d) => d.id)
  );

  if (freshIds.length === 0) {
    pass();
    return;
  }

  const freshDocs = docs.filter((d) => freshIds.includes(d.id));

  // Format concise context
  const lines = freshDocs.map((d, i) => {
    const score = Math.round(d.score * 100);
    const snippet = d.text.slice(0, 300).replace(/\n/g, " ");
    return `${i + 1}. [${score}%] ${snippet}`;
  });

  const context = `Relevant context from Moss (index: ${settings.indexName}):\n\n${lines.join("\n\n")}`;

  saveState(sessionId, state);

  writeOutput({
    hookSpecificOutput: {
      hookEventName: "UserPromptSubmit",
      additionalContext: context,
    },
  });
}

main().catch(() => {
  pass();
});

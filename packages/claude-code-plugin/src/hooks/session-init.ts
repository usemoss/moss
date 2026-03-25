// SessionStart hook — plain stdout, exit 0.
// No JSON output. No cloud calls. Just report env var status.

const projectId = process.env.MOSS_PROJECT_ID;
const projectKey = process.env.MOSS_PROJECT_KEY;

if (!projectId || !projectKey) {
  console.log(
    "Moss: set MOSS_PROJECT_ID and MOSS_PROJECT_KEY environment variables to enable semantic search."
  );
  process.exit(0);
}

const indexName = process.env.MOSS_INDEX_NAME || "not set";
const autoSearch = process.env.MOSS_AUTO_SEARCH !== "false" ? "on" : "off";

console.log(`Moss ready. Index: ${indexName}. Auto-search: ${autoSearch}`);
process.exit(0);

// SessionStart hook — plain stdout, exit 0.
import { loadSettings } from "../lib/settings.js";

const settings = loadSettings();

if (!settings) {
  console.log(
    "Moss: configure ~/.moss-claude/settings.json with projectId and projectKey to enable."
  );
  process.exit(0);
}

const indexName = settings.indexName || "not set";
const autoSearch = settings.autoSearch ? "on" : "off";

console.log(`Moss ready. Index: ${indexName}. Auto-search: ${autoSearch}`);
process.exit(0);

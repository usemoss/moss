"use strict";

// src/hooks/session-init.ts
var projectId = process.env.MOSS_PROJECT_ID;
var projectKey = process.env.MOSS_PROJECT_KEY;
if (!projectId || !projectKey) {
  console.log(
    "Moss: set MOSS_PROJECT_ID and MOSS_PROJECT_KEY environment variables to enable semantic search."
  );
  process.exit(0);
}
var indexName = process.env.MOSS_INDEX_NAME || "not set";
var autoSearch = process.env.MOSS_AUTO_SEARCH !== "false" ? "on" : "off";
console.log(`Moss ready. Index: ${indexName}. Auto-search: ${autoSearch}`);
process.exit(0);

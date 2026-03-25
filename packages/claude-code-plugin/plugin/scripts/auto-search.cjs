"use strict";
var __create = Object.create;
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __getProtoOf = Object.getPrototypeOf;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(
  // If the importer is in node compatibility mode or this is not an ESM
  // file that has been converted to a CommonJS file using a Babel-
  // compatible transform (i.e. "__esModule" has not been set), then set
  // "default" to the CommonJS "module.exports" for node compatibility.
  isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", { value: mod, enumerable: true }) : target,
  mod
));

// src/lib/stdin.ts
function readStdin() {
  return new Promise((resolve, reject) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => {
      data += chunk;
    });
    process.stdin.on("end", () => {
      try {
        resolve(data.trim() ? JSON.parse(data) : {});
      } catch (err) {
        reject(new Error(`Failed to parse stdin JSON: ${err.message}`));
      }
    });
    process.stdin.on("error", reject);
    if (process.stdin.isTTY) resolve({});
  });
}
function writeOutput(data) {
  console.log(JSON.stringify(data));
}

// src/lib/settings.ts
var fs = __toESM(require("node:fs"), 1);
var path = __toESM(require("node:path"), 1);
function loadSettingsFile() {
  const dataDir = process.env.CLAUDE_PLUGIN_DATA;
  if (!dataDir) return {};
  const settingsPath = path.join(dataDir, "settings.json");
  try {
    if (fs.existsSync(settingsPath)) {
      return JSON.parse(fs.readFileSync(settingsPath, "utf-8"));
    }
  } catch {
  }
  return {};
}
function loadSettings() {
  const file = loadSettingsFile();
  const projectId = process.env.MOSS_PROJECT_ID || file.projectId;
  const projectKey = process.env.MOSS_PROJECT_KEY || file.projectKey;
  if (!projectId || !projectKey) return null;
  return {
    projectId,
    projectKey,
    indexName: process.env.MOSS_INDEX_NAME || file.indexName,
    autoSearch: process.env.MOSS_AUTO_SEARCH !== "false" && file.autoSearch !== false,
    topK: file.topK ?? 3,
    scoreThreshold: file.scoreThreshold ?? 0.3
  };
}

// src/lib/state.ts
var fs2 = __toESM(require("node:fs"), 1);
var path2 = __toESM(require("node:path"), 1);
var MAX_SEEN = 50;
function statePath(sessionId) {
  const dataDir = process.env.CLAUDE_PLUGIN_DATA || "/tmp/claude-moss";
  return path2.join(dataDir, "state", `${sessionId}.json`);
}
function loadState(sessionId) {
  try {
    const file = statePath(sessionId);
    if (fs2.existsSync(file)) {
      return JSON.parse(fs2.readFileSync(file, "utf-8"));
    }
  } catch {
  }
  return { seenDocIds: [] };
}
function saveState(sessionId, state) {
  try {
    const file = statePath(sessionId);
    fs2.mkdirSync(path2.dirname(file), { recursive: true });
    fs2.writeFileSync(file, JSON.stringify(state));
  } catch {
  }
}
function dedup(state, docIds) {
  const seen = new Set(state.seenDocIds);
  const fresh = docIds.filter((id) => !seen.has(id));
  state.seenDocIds = [...state.seenDocIds, ...fresh].slice(-MAX_SEEN);
  return fresh;
}

// src/lib/trigger.ts
var KNOWLEDGE_PATTERNS = [
  /\bhow\s+does\b/i,
  /\bwhere\s+is\b/i,
  /\bwhy\s+does\b/i,
  /\bwhy\s+is\b/i,
  /\bwhat\s+is\s+the\b/i,
  /\bexplain\b/i,
  /\bwhat\s+does\b/i,
  /\bhow\s+to\b/i
];
var SEARCH_PATTERNS = [
  /\bfind\b/i,
  /\bsearch\b/i,
  /\blook\s*up\b/i,
  /\bretrieve\b/i
];
var DEBUG_PATTERNS = [
  /\bbroken\b/i,
  /\bfailing\b/i,
  /\berror\b/i,
  /\bbug\b/i,
  /\bcrash\b/i,
  /\bexception\b/i,
  /\bnot\s+working\b/i
];
var ARCHITECTURE_PATTERNS = [
  /\barchitecture\b/i,
  /\bdesign\b/i,
  /\bpattern\b/i,
  /\bimplementation\b/i,
  /\bhow\s+.*\s+works?\b/i
];
var ALL_TRIGGER_PATTERNS = [
  ...KNOWLEDGE_PATTERNS,
  ...SEARCH_PATTERNS,
  ...DEBUG_PATTERNS,
  ...ARCHITECTURE_PATTERNS
];
var SKIP_PATTERNS = [
  /^(change|rename|replace|update|set|move)\s/i,
  /^(write|create|implement|add|build|make)\s+(a\s+)?(function|class|method|component|test)/i,
  /^fix\s+(the\s+)?typo/i,
  /^(refactor|rewrite)\s+this/i
];
function shouldTrigger(prompt) {
  const trimmed = prompt.trim();
  if (trimmed.length < 10 || trimmed.length > 500) return false;
  for (const pattern of SKIP_PATTERNS) {
    if (pattern.test(trimmed)) return false;
  }
  for (const pattern of ALL_TRIGGER_PATTERNS) {
    if (pattern.test(trimmed)) return true;
  }
  if (trimmed.includes("?")) return true;
  return false;
}

// src/lib/moss-rest.ts
var BASE_URL = "https://service.usemoss.dev";
var QUERY_URL = `${BASE_URL}/query`;
var MANAGE_URL = `${BASE_URL}/v1/manage`;
async function cloudQuery(opts) {
  const res = await fetch(QUERY_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query: opts.query,
      indexName: opts.indexName,
      projectId: opts.projectId,
      projectKey: opts.projectKey,
      topK: opts.topK ?? 3
    }),
    signal: AbortSignal.timeout(4e3)
  });
  if (!res.ok) throw new Error(`Moss /query: HTTP ${res.status}`);
  return await res.json();
}

// src/hooks/auto-search.ts
var pass = () => writeOutput({ continue: true });
async function main() {
  const input = await readStdin();
  const settings = loadSettings();
  if (!settings || !settings.indexName || !settings.autoSearch) {
    pass();
    return;
  }
  const prompt = (input.prompt || "").trim();
  if (!shouldTrigger(prompt)) {
    pass();
    return;
  }
  const result = await cloudQuery({
    projectId: settings.projectId,
    projectKey: settings.projectKey,
    indexName: settings.indexName,
    query: prompt,
    topK: settings.topK
  });
  const docs = (result.docs || []).filter(
    (d) => d.score >= settings.scoreThreshold
  );
  if (docs.length === 0) {
    pass();
    return;
  }
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
  const lines = freshDocs.map((d, i) => {
    const score = Math.round(d.score * 100);
    const snippet = d.text.slice(0, 300).replace(/\n/g, " ");
    return `${i + 1}. [${score}%] ${snippet}`;
  });
  const context = `Relevant context from Moss (index: ${settings.indexName}):

${lines.join("\n\n")}`;
  saveState(sessionId, state);
  writeOutput({
    hookSpecificOutput: {
      hookEventName: "UserPromptSubmit",
      additionalContext: context
    }
  });
}
main().catch(() => {
  pass();
});

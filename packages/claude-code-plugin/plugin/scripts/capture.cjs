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
var os = __toESM(require("node:os"), 1);
var SETTINGS_FILE = path.join(os.homedir(), ".moss-claude", "settings.json");
function loadSettingsFile() {
  try {
    if (fs.existsSync(SETTINGS_FILE)) {
      return JSON.parse(fs.readFileSync(SETTINGS_FILE, "utf-8"));
    }
  } catch {
  }
  const dataDir = process.env.CLAUDE_PLUGIN_DATA;
  if (dataDir) {
    try {
      const p = path.join(dataDir, "settings.json");
      if (fs.existsSync(p)) {
        return JSON.parse(fs.readFileSync(p, "utf-8"));
      }
    } catch {
    }
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

// src/lib/transcript.ts
var fs3 = __toESM(require("node:fs"), 1);
function extractTextContent(message) {
  if (!message?.content) return null;
  const content = message.content;
  if (typeof content === "string") return content.trim() || null;
  if (Array.isArray(content)) {
    const texts = content.filter((block) => block.type === "text" && block.text).map((block) => block.text.trim()).filter(Boolean);
    return texts.length > 0 ? texts.join("\n\n") : null;
  }
  return null;
}
function extractNewMessages(transcriptPath, lastUuid) {
  if (!fs3.existsSync(transcriptPath)) return null;
  const raw = fs3.readFileSync(transcriptPath, "utf-8");
  const entries = raw.trim().split("\n").filter((line) => line.trim()).map((line) => {
    try {
      return JSON.parse(line);
    } catch {
      return null;
    }
  }).filter(Boolean);
  if (entries.length === 0) return null;
  let startIndex = 0;
  if (lastUuid) {
    const idx = entries.findIndex((e) => e.uuid === lastUuid);
    if (idx >= 0) startIndex = idx + 1;
  }
  const newEntries = entries.slice(startIndex).filter((e) => e.type === "user" || e.type === "assistant");
  if (newEntries.length === 0) return null;
  const messages = newEntries.map((entry) => {
    const content = extractTextContent(entry.message);
    if (!content) return null;
    return { role: entry.type, content };
  }).filter(Boolean);
  if (messages.length === 0) return null;
  const newLastUuid = newEntries[newEntries.length - 1].uuid;
  return { messages, lastUuid: newLastUuid };
}

// src/lib/moss-rest.ts
var BASE_URL = "https://service.usemoss.dev";
var QUERY_URL = `${BASE_URL}/query`;
var MANAGE_URL = `${BASE_URL}/v1/manage`;
async function manage(opts) {
  const res = await fetch(MANAGE_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Project-Key": opts.projectKey
    },
    body: JSON.stringify({
      action: opts.action,
      projectId: opts.projectId,
      ...opts.data
    }),
    signal: AbortSignal.timeout(6e4)
  });
  if (!res.ok) throw new Error(`Moss /v1/manage ${opts.action}: HTTP ${res.status}`);
  return res.json();
}
async function cloudAddDocs(opts) {
  return manage({
    projectId: opts.projectId,
    projectKey: opts.projectKey,
    action: "addDocs",
    data: {
      indexName: opts.indexName,
      docs: opts.docs,
      options: { upsert: opts.upsert ?? true }
    }
  });
}

// src/hooks/capture.ts
var pass = () => writeOutput({ continue: true });
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
  const result = extractNewMessages(transcriptPath, state.lastUuid || null);
  if (!result) {
    pass();
    return;
  }
  const docs = result.messages.map((msg, i) => ({
    id: `session-${sessionId}-${(state.lastUuid || "0").slice(0, 8)}-${i}`,
    text: `[${msg.role}] ${msg.content}`,
    metadata: {
      sessionId,
      role: msg.role,
      source: "conversation",
      capturedAt: (/* @__PURE__ */ new Date()).toISOString()
    }
  }));
  try {
    await cloudAddDocs({
      projectId: settings.projectId,
      projectKey: settings.projectKey,
      indexName: settings.indexName,
      docs
    });
  } catch {
  }
  state.lastUuid = result.lastUuid;
  saveState(sessionId, state);
  pass();
}
main().catch(() => {
  pass();
});

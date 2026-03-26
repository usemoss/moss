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
    localServer: file.localServer !== false,
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
var SKIP = [
  /^(change|rename|replace|update|set|move)\s/i,
  /^(write|create|implement|add|build|make)\s+(a\s+)?(function|class|method|component|test)/i,
  /^fix\s+(the\s+)?typo/i,
  /^(refactor|rewrite)\s+this/i
];
function shouldTrigger(prompt) {
  const t = prompt.trim();
  if (t.length < 10) return false;
  for (const r of SKIP) if (r.test(t)) return false;
  return true;
}

// src/lib/local-query.ts
var net = __toESM(require("node:net"), 1);
var fs3 = __toESM(require("node:fs"), 1);
var SOCKET_PATH = "/tmp/moss-claude/query.sock";
var TIMEOUT_MS = 1500;
async function localQuery(opts) {
  if (!fs3.existsSync(SOCKET_PATH)) {
    throw new Error("Local query socket not found");
  }
  return new Promise((resolve, reject) => {
    const socket = net.createConnection(SOCKET_PATH);
    const chunks = [];
    let settled = false;
    const timer = setTimeout(() => {
      if (!settled) {
        settled = true;
        socket.destroy();
        reject(new Error("Local query timeout"));
      }
    }, TIMEOUT_MS);
    socket.on("connect", () => {
      const req = JSON.stringify({
        query: opts.query,
        indexName: opts.indexName,
        topK: opts.topK ?? 10
      });
      socket.write(req + "\n");
    });
    socket.on("data", (chunk) => {
      chunks.push(chunk);
    });
    socket.on("end", () => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      try {
        const data = Buffer.concat(chunks).toString("utf-8").trim();
        const result = JSON.parse(data);
        resolve(result);
      } catch (err) {
        reject(new Error("Invalid response from local server"));
      }
    });
    socket.on("error", (err) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      reject(err);
    });
  });
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
  const result = await localQuery({
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

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

// src/hooks/session-init.ts
var fs2 = __toESM(require("node:fs"), 1);
var os2 = __toESM(require("node:os"), 1);
var path2 = __toESM(require("node:path"), 1);
var import_node_child_process = require("node:child_process");

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

// src/hooks/session-init.ts
var SOCKET_DIR = "/tmp/moss-claude";
var PID_PATH = path2.join(SOCKET_DIR, "query.pid");
var SOCKET_PATH = path2.join(SOCKET_DIR, "query.sock");
var settings = loadSettings();
if (!settings) {
  console.log(
    "Moss: configure ~/.moss-claude/settings.json with projectId and projectKey to enable."
  );
  process.exit(0);
}
var indexName = settings.indexName || "not set";
var autoSearch = settings.autoSearch ? "on" : "off";
console.log(`Moss ready. Index: ${indexName}. Auto-search: ${autoSearch}`);
if (settings.indexName && settings.localServer) {
  let alreadyRunning = false;
  try {
    if (fs2.existsSync(PID_PATH)) {
      const pid = parseInt(fs2.readFileSync(PID_PATH, "utf-8").trim(), 10);
      if (pid > 0) {
        process.kill(pid, 0);
        alreadyRunning = true;
      }
    }
  } catch {
    try {
      fs2.unlinkSync(PID_PATH);
    } catch {
    }
    try {
      fs2.unlinkSync(SOCKET_PATH);
    } catch {
    }
  }
  if (!alreadyRunning) {
    const pluginRoot = process.env.CLAUDE_PLUGIN_ROOT || path2.resolve(path2.dirname(process.argv[1]), "..");
    const serverScript = path2.join(pluginRoot, "scripts", "local-server.cjs");
    if (fs2.existsSync(serverScript)) {
      fs2.mkdirSync(SOCKET_DIR, { recursive: true });
      const candidatePaths = [
        path2.join(pluginRoot, "node_modules"),
        path2.join(pluginRoot, "..", "..", "node_modules"),
        // Marketplace source (where npm install was run during development)
        path2.resolve(os2.homedir(), ".claude/plugins/marketplaces/moss/packages/claude-code-plugin/node_modules"),
        path2.resolve(os2.homedir(), ".claude/plugins/marketplaces/moss/node_modules")
      ];
      try {
        const globalRoot = (0, import_node_child_process.execFileSync)("npm", ["root", "-g"], { encoding: "utf-8" }).trim();
        if (globalRoot) candidatePaths.push(globalRoot);
      } catch {
      }
      const extraNodePaths = candidatePaths.filter((p) => fs2.existsSync(p));
      const existingNodePath = process.env.NODE_PATH || "";
      const nodePath = [...extraNodePaths, existingNodePath].filter(Boolean).join(path2.delimiter);
      const child = (0, import_node_child_process.spawn)(
        "node",
        [serverScript, settings.projectId, settings.projectKey, settings.indexName],
        {
          detached: true,
          stdio: ["ignore", "ignore", "inherit"],
          env: { ...process.env, NODE_PATH: nodePath }
        }
      );
      child.unref();
      process.stderr.write(
        `[moss] Starting local query server (pid: ${child.pid})
`
      );
    }
  }
}
process.exit(0);

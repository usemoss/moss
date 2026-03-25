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

// src/hooks/session-init.ts
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
process.exit(0);

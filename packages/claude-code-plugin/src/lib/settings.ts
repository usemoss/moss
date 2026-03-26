import * as fs from "node:fs";
import * as path from "node:path";
import * as os from "node:os";

export interface MossSettings {
  projectId: string;
  projectKey: string;
  indexName?: string;
  autoSearch: boolean;
  localServer: boolean;
  topK: number;
  scoreThreshold: number;
}

interface SettingsFile {
  projectId?: string;
  projectKey?: string;
  indexName?: string;
  autoSearch?: boolean;
  localServer?: boolean;
  topK?: number;
  scoreThreshold?: number;
}

const SETTINGS_FILE = path.join(os.homedir(), ".moss-claude", "settings.json");

function loadSettingsFile(): SettingsFile {
  // Try ~/.moss-claude/settings.json first
  try {
    if (fs.existsSync(SETTINGS_FILE)) {
      return JSON.parse(fs.readFileSync(SETTINGS_FILE, "utf-8"));
    }
  } catch { /* ignore */ }

  // Fallback to CLAUDE_PLUGIN_DATA/settings.json
  const dataDir = process.env.CLAUDE_PLUGIN_DATA;
  if (dataDir) {
    try {
      const p = path.join(dataDir, "settings.json");
      if (fs.existsSync(p)) {
        return JSON.parse(fs.readFileSync(p, "utf-8"));
      }
    } catch { /* ignore */ }
  }

  return {};
}

export function loadSettings(): MossSettings | null {
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
    scoreThreshold: file.scoreThreshold ?? 0.3,
  };
}

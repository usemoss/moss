import * as fs from "node:fs";
import * as path from "node:path";

export interface MossSettings {
  projectId: string;
  projectKey: string;
  indexName?: string;
  autoSearch: boolean;
  topK: number;
  scoreThreshold: number;
}

interface SettingsFile {
  projectId?: string;
  projectKey?: string;
  indexName?: string;
  autoSearch?: boolean;
  topK?: number;
  scoreThreshold?: number;
}

function loadSettingsFile(): SettingsFile {
  const dataDir = process.env.CLAUDE_PLUGIN_DATA;
  if (!dataDir) return {};

  const settingsPath = path.join(dataDir, "settings.json");
  try {
    if (fs.existsSync(settingsPath)) {
      return JSON.parse(fs.readFileSync(settingsPath, "utf-8"));
    }
  } catch {
    // Silently ignore malformed settings file
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
    topK: file.topK ?? 3,
    scoreThreshold: file.scoreThreshold ?? 0.3,
  };
}

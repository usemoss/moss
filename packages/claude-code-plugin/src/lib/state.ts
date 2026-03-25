import * as fs from "node:fs";
import * as path from "node:path";

const MAX_SEEN = 50;

export interface SessionState {
  seenDocIds: string[];
  lastUuid?: string;
}

function statePath(sessionId: string): string {
  const dataDir = process.env.CLAUDE_PLUGIN_DATA || "/tmp/claude-moss";
  return path.join(dataDir, "state", `${sessionId}.json`);
}

export function loadState(sessionId: string): SessionState {
  try {
    const file = statePath(sessionId);
    if (fs.existsSync(file)) {
      return JSON.parse(fs.readFileSync(file, "utf-8"));
    }
  } catch {
    // Corrupted state — start fresh
  }
  return { seenDocIds: [] };
}

export function saveState(sessionId: string, state: SessionState): void {
  try {
    const file = statePath(sessionId);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, JSON.stringify(state));
  } catch {
    // Best-effort — don't break the hook if state can't be written
  }
}

/**
 * Filter out already-seen doc IDs and update the bounded buffer.
 * Returns only the new (unseen) IDs.
 */
export function dedup(state: SessionState, docIds: string[]): string[] {
  const seen = new Set(state.seenDocIds);
  const fresh = docIds.filter((id) => !seen.has(id));

  // Append new IDs and trim to bounded size
  state.seenDocIds = [...state.seenDocIds, ...fresh].slice(-MAX_SEEN);

  return fresh;
}

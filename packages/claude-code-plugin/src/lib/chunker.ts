import * as crypto from "node:crypto";

export interface Chunk {
  id: string;
  text: string;
  metadata: Record<string, string>;
}

export interface FileManifestEntry {
  hash: string;
  chunkIds: string[];
}

export type Manifest = Record<string, FileManifestEntry>;

// Moss recommends 200-500 tokens per chunk with 10-20% overlap.
// ~60 lines ≈ 300-400 tokens for typical code. Overlap = ~10 lines.
const MAX_CHUNK_LINES = 60;
const OVERLAP_LINES = 8;
const MAX_CHUNK_CHARS = 2500;

const EXT_TO_LANG: Record<string, string> = {
  ts: "typescript", tsx: "typescript", js: "javascript", jsx: "javascript",
  py: "python", rs: "rust", go: "go", java: "java", rb: "ruby",
  md: "markdown", json: "json", yaml: "yaml", yml: "yaml",
  css: "css", html: "html", sql: "sql", sh: "shell",
};

export function hashContent(content: string): string {
  return crypto.createHash("sha256").update(content).digest("hex").slice(0, 16);
}

function detectLanguage(filePath: string): string {
  const ext = filePath.split(".").pop() || "";
  return EXT_TO_LANG[ext] || "text";
}

/**
 * Chunk a file into ~60-line segments with 10-20% overlap and file path metadata.
 * Aligned with Moss recommendation: 200-500 tokens/chunk, overlap for context continuity.
 */
export function chunkFile(filePath: string, content: string): Chunk[] {
  const lines = content.split("\n");
  const language = detectLanguage(filePath);
  const chunks: Chunk[] = [];

  let start = 0;
  while (start < lines.length) {
    let end = Math.min(start + MAX_CHUNK_LINES, lines.length);

    // Try to break at a blank line for cleaner boundaries
    if (end < lines.length) {
      for (let i = end; i > start + Math.floor(MAX_CHUNK_LINES / 2); i--) {
        if (lines[i]?.trim() === "") {
          end = i;
          break;
        }
      }
    }

    const slice = lines.slice(start, end).join("\n");

    // Skip empty chunks
    if (slice.trim().length === 0) {
      start = end - OVERLAP_LINES;
      if (start <= (chunks.length > 0 ? end - MAX_CHUNK_LINES : 0)) start = end;
      continue;
    }

    // Enforce char limit
    const text = slice.length > MAX_CHUNK_CHARS
      ? slice.slice(0, MAX_CHUNK_CHARS)
      : slice;

    const startLine = start + 1;
    const endLine = end;
    const id = `${filePath}:${startLine}-${endLine}`;

    chunks.push({
      id,
      text: `File: ${filePath} (lines ${startLine}-${endLine})\n\n${text}`,
      metadata: {
        filePath,
        startLine: String(startLine),
        endLine: String(endLine),
        language,
      },
    });

    // Advance with overlap for context continuity
    start = end - OVERLAP_LINES;
    if (start <= (chunks.length > 1 ? end - MAX_CHUNK_LINES : 0)) start = end;
  }

  return chunks;
}

import type { DocumentInfo } from "@moss-dev/moss";
import * as path from "node:path";

const MAX_CHARS_PER_CHUNK = 2400;
const OVERLAP_LINES = 2;

function languageFromPath(filePath: string): string {
  const ext = path.extname(filePath).toLowerCase().replace(".", "");
  return ext || "text";
}

/**
 * Split file contents into fixed-size line-based chunks with stable IDs.
 */
export function chunkFile(
  relativePath: string,
  content: string,
): DocumentInfo[] {
  const normalized = content.replace(/\r\n/g, "\n");
  if (!normalized.trim()) {
    return [];
  }

  const lines = normalized.split("\n");
  const language = languageFromPath(relativePath);
  const docs: DocumentInfo[] = [];

  let chunkIndex = 0;
  let start = 0;

  while (start < lines.length) {
    let end = start;
    let size = 0;

    while (end < lines.length) {
      const lineLen = lines[end].length + 1;
      if (size > 0 && size + lineLen > MAX_CHARS_PER_CHUNK) {
        break;
      }
      size += lineLen;
      end += 1;
    }

    if (end === start) {
      end = start + 1;
    }

    const slice = lines.slice(start, end).join("\n");
    const startLine = start + 1;
    const endLine = end;

    docs.push({
      id: `${relativePath}#chunk-${chunkIndex}`,
      text: slice,
      metadata: {
        filePath: relativePath,
        startLine: String(startLine),
        endLine: String(endLine),
        language,
        chunkIndex: String(chunkIndex),
      },
    });

    chunkIndex += 1;
    if (end >= lines.length) {
      break;
    }
    start = Math.max(end - OVERLAP_LINES, start + 1);
  }

  return docs;
}

export function chunkIdsForPath(relativePath: string, count: number): string[] {
  return Array.from({ length: count }, (_, i) => `${relativePath}#chunk-${i}`);
}

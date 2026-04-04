import type { MossDocument, MossMetadata } from "./types.js";

const DEFAULT_MAX_CHARS = 12_000;
const DEFAULT_SMALL_FILE_LINES = 50;

export interface ChunkOptions {
  chunkMaxLines: number;
  chunkOverlapLines: number;
  /** Upper bound on embedded text length per chunk (Phase 0: ~12k). */
  maxCharsPerChunk?: number;
  /** If total lines ≤ this, emit a single chunk for the whole file. */
  smallFileMaxLines?: number;
  workspaceFolderIndex?: number;
  workspaceFolderName?: string;
  /**
   * Uniquifies doc ids across workspace roots (e.g. multi-root). Omitted for single-folder workspaces.
   */
  chunkIdNamespace?: string;
}

function normalizeRelativePath(relativePath: string): string {
  return relativePath.replace(/\\/g, "/");
}

function joinLines(lines: string[], startIdx: number, endIdxExclusive: number): string {
  return lines.slice(startIdx, endIdxExclusive).join("\n");
}

function truncateToMaxChars(
  lines: string[],
  startIdx: number,
  endIdxExclusive: number,
  maxChars: number
): { text: string; endIdxExclusive: number } {
  let end = endIdxExclusive;
  let text = joinLines(lines, startIdx, end);
  while (text.length > maxChars && end > startIdx + 1) {
    end -= 1;
    text = joinLines(lines, startIdx, end);
  }
  if (text.length > maxChars && end === startIdx + 1) {
    const line = lines[startIdx] ?? "";
    text = line.slice(0, maxChars);
  }
  return { text, endIdxExclusive: end };
}

function buildMetadata(
  pathNorm: string,
  startLine1: number,
  endLine1: number,
  options: ChunkOptions
): MossMetadata {
  const meta: MossMetadata = {
    path: pathNorm,
    startLine: String(startLine1),
    endLine: String(endLine1),
  };
  if (options.workspaceFolderIndex !== undefined) {
    meta.workspaceFolderIndex = String(options.workspaceFolderIndex);
  }
  if (options.workspaceFolderName !== undefined) {
    meta.workspaceFolderName = options.workspaceFolderName;
  }
  return meta;
}

/**
 * Split file text into Moss documents with stable ids `path:startLine-endLine`.
 * Line numbers are 1-based inclusive in metadata. Pure — no VS Code API.
 */
export function chunkFileContent(
  relativePath: string,
  text: string,
  options: ChunkOptions
): MossDocument[] {
  const pathNorm = normalizeRelativePath(relativePath);
  const lines = text.split(/\r?\n/);
  const total = lines.length;

  const maxLines = Math.max(1, options.chunkMaxLines);
  let overlap = Math.max(0, options.chunkOverlapLines);
  if (overlap >= maxLines) {
    overlap = Math.max(0, maxLines - 1);
  }
  const maxChars = options.maxCharsPerChunk ?? DEFAULT_MAX_CHARS;
  const smallMax = options.smallFileMaxLines ?? DEFAULT_SMALL_FILE_LINES;

  const docs: MossDocument[] = [];

  const idPrefix =
    options.chunkIdNamespace !== undefined && options.chunkIdNamespace !== ""
      ? `${options.chunkIdNamespace}:`
      : "";

  if (total === 0) {
    docs.push({
      id: `${idPrefix}${pathNorm}:1-1`,
      text: "",
      metadata: buildMetadata(pathNorm, 1, 1, options),
    });
    return docs;
  }

  if (total <= smallMax) {
    const { text: body, endIdxExclusive } = truncateToMaxChars(
      lines,
      0,
      total,
      maxChars
    );
    const endLine = endIdxExclusive;
    docs.push({
      id: `${idPrefix}${pathNorm}:1-${endLine}`,
      text: body,
      metadata: buildMetadata(pathNorm, 1, endLine, options),
    });
    return docs;
  }

  let startLine = 1;
  while (startLine <= total) {
    const startIdx = startLine - 1;
    let endLine = Math.min(total, startLine + maxLines - 1);
    let endIdxExclusive = endLine;

    const { text: body, endIdxExclusive: trimmedEnd } = truncateToMaxChars(
      lines,
      startIdx,
      endIdxExclusive,
      maxChars
    );
    endIdxExclusive = trimmedEnd;
    endLine = endIdxExclusive;

    docs.push({
      id: `${idPrefix}${pathNorm}:${startLine}-${endLine}`,
      text: body,
      metadata: buildMetadata(pathNorm, startLine, endLine, options),
    });

    if (endLine >= total) break;
    const nextStart = Math.max(startLine + 1, endLine - overlap + 1);
    startLine = nextStart;
  }

  return docs;
}

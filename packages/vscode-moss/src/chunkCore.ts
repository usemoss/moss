import type { MossDocument, MossMetadata } from "./types.js";

const DEFAULT_MAX_CHARS = 12_000;

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

export function normalizeRelativePath(relativePath: string): string {
  return relativePath.replace(/\\/g, "/");
}

function joinLines(
  lines: string[],
  startIdx: number,
  endIdxExclusive: number
): string {
  return lines.slice(startIdx, endIdxExclusive).join("\n");
}

export function truncateToMaxChars(
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

export function buildMetadata(
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
 * Line-window chunking for lines [segmentStartLine1, segmentEndLine1] inclusive (1-based).
 */
export function chunkLineWindowSegment(
  pathNorm: string,
  lines: string[],
  segmentStartLine1: number,
  segmentEndLine1: number,
  options: ChunkOptions,
  idPrefix: string,
  metaForRange: (startLine1: number, endLine1: number) => MossMetadata
): MossDocument[] {
  const total = lines.length;
  const segStart = Math.max(1, Math.min(segmentStartLine1, total || 1));
  const segEnd = Math.max(segStart, Math.min(segmentEndLine1, total || 1));
  const segLen = segEnd - segStart + 1;

  const maxLines = Math.max(1, options.chunkMaxLines);
  let overlap = Math.max(0, options.chunkOverlapLines);
  if (overlap >= maxLines) {
    overlap = Math.max(0, maxLines - 1);
  }
  const maxChars = options.maxCharsPerChunk ?? DEFAULT_MAX_CHARS;

  const docs: MossDocument[] = [];

  if (segLen <= 0) return docs;

  let startLine = segStart;
  while (startLine <= segEnd) {
    const startIdx = startLine - 1;
    let endLine = Math.min(segEnd, startLine + maxLines - 1);
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
      metadata: metaForRange(startLine, endLine),
    });

    if (endLine >= segEnd) break;
    const nextStart = Math.max(startLine + 1, endLine - overlap + 1);
    startLine = nextStart;
  }

  return docs;
}

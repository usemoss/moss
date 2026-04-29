import {
  supportsStructureChunking,
  tryStructureAwareChunk,
} from "./structureChunking.js";
import {
  buildMetadata,
  chunkLineWindowSegment,
  DEFAULT_MAX_CHARS,
  normalizeRelativePath,
  truncateToMaxChars,
} from "./chunkCore.js";

import type { DocumentInfo } from "@moss-dev/moss";
import type { ChunkOptions } from "./chunkCore.js";

export type { ChunkOptions };

const DEFAULT_SMALL_FILE_LINES = 50;

/**
 * Full-file line-window chunking (fallback when structure-aware path does not apply).
 */
export function chunkFileContentLineWindowsOnly(
  relativePath: string,
  text: string,
  options: ChunkOptions
): DocumentInfo[] {
  const pathNorm = normalizeRelativePath(relativePath);
  const lines = text.split(/\r?\n/);
  const total = lines.length;

  const maxChars = options.maxCharsPerChunk ?? DEFAULT_MAX_CHARS;
  const smallMax = options.smallFileMaxLines ?? DEFAULT_SMALL_FILE_LINES;

  const idPrefix =
    options.chunkIdNamespace !== undefined && options.chunkIdNamespace !== ""
      ? `${options.chunkIdNamespace}:`
      : "";

  if (total === 0) {
    return [
      {
        id: `${idPrefix}${pathNorm}:1-1`,
        text: "",
        metadata: buildMetadata(pathNorm, 1, 1, options),
      },
    ];
  }

  if (total <= smallMax) {
    const { text: body, endIdxExclusive } = truncateToMaxChars(
      lines,
      0,
      total,
      maxChars
    );
    const endLine = endIdxExclusive;
    return [
      {
        id: `${idPrefix}${pathNorm}:1-${endLine}`,
        text: body,
        metadata: buildMetadata(pathNorm, 1, endLine, options),
      },
    ];
  }

  return chunkLineWindowSegment(
    pathNorm,
    lines,
    1,
    total,
    options,
    idPrefix,
    (sl, el) => buildMetadata(pathNorm, sl, el, options)
  );
}

/**
 * Split file text into Moss documents. Uses Markdown / JS / TS structure when applicable,
 * otherwise overlapping line windows via {@link chunkFileContentLineWindowsOnly}.
 */
export async function chunkFileContent(
  relativePath: string,
  text: string,
  options: ChunkOptions,
  languageId?: string
): Promise<DocumentInfo[]> {
  const lines = text.split(/\r?\n/);
  const total = lines.length;

  if (total > 0 && supportsStructureChunking(languageId)) {
    const structured = await tryStructureAwareChunk(
      relativePath,
      text,
      lines,
      options,
      languageId
    );
    if (structured && structured.length > 0) {
      return structured;
    }
  }

  return chunkFileContentLineWindowsOnly(relativePath, text, options);
}

export type { DocumentInfo, QueryResultDocumentInfo } from "@moss-dev/moss";

/**
 * Moss REST/SDK documents use string-only metadata values.
 */
export type MossMetadata = Record<string, string>;

/** Chunk metadata we store for workspace indexing (all values are strings in Moss). */
export interface ChunkMetadata {
  path: string;
  startLine: string;
  endLine: string;
  workspaceFolderIndex?: string;
  workspaceFolderName?: string;
}

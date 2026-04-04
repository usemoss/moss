/**
 * Moss REST/SDK documents use string-only metadata values.
 */
export type MossMetadata = Record<string, string>;

/** One chunk uploaded to Moss (aligned with @inferedge-rest/moss DocumentInfo). */
export interface MossDocument {
  id: string;
  text: string;
  metadata: MossMetadata;
}

/** Chunk metadata we store for workspace indexing (all values are strings in Moss). */
export interface ChunkMetadata {
  path: string;
  startLine: string;
  endLine: string;
  workspaceFolderIndex?: string;
  workspaceFolderName?: string;
}

/** Normalized search result for the webview / navigation (Phase 6–7). */
export interface SearchHit {
  id: string;
  score: number;
  text: string;
  metadata: MossMetadata;
}

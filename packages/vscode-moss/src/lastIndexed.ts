/** `workspaceState` key written after a successful **Moss: Index Workspace**. */
export const MOSS_LAST_INDEXED_KEY = "moss.lastIndexed";

export interface LastIndexedState {
  indexName: string;
  docCount: number;
  fileCount: number;
  timestamp: number;
}

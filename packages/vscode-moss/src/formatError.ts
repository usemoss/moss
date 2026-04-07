/** Stable string for logging and user-facing error messages. */
export function formatError(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

import type * as vscode from "vscode";
import { getMossLogVerbose } from "./config.js";

type LogSink = Pick<vscode.OutputChannel, "appendLine">;

/**
 * Append a line to the Moss output channel. Use **`verbose`** for optional detail when
 * **`moss.logVerbose`** is enabled (Phase 8).
 */
export function mossLog(
  sink: LogSink,
  line: string,
  level: "always" | "verbose" = "always"
): void {
  if (level === "verbose" && !getMossLogVerbose()) return;
  sink.appendLine(line);
}

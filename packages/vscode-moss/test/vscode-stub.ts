/**
 * Minimal `vscode` surface for unit tests (Vitest resolves `vscode` here via alias).
 * Supports `paths.ts`, `config.ts`, and any module that only needs Uri / Range / workspace config.
 */
import { URI, Utils } from "vscode-uri";

export class Position {
  constructor(
    public readonly line: number,
    public readonly character: number
  ) {}
}

export class Range {
  public readonly start: Position;
  public readonly end: Position;
  constructor(startLine: number, startChar: number, endLine: number, endChar: number) {
    this.start = new Position(startLine, startChar);
    this.end = new Position(endLine, endChar);
  }
}

export const Uri = {
  file: (fsPath: string): URI => URI.file(fsPath),
  joinPath: (base: URI, ...pathSegments: string[]): URI =>
    Utils.joinPath(base, ...pathSegments),
};

const mossConfigByScope = new Map<string, Record<string, unknown>>();

export function resetMossTestConfig(): void {
  mossConfigByScope.clear();
}

/** Keys match `get("indexName")` etc. on the `moss` configuration section (no credential keys). */
export function setMossTestConfig(
  resourceUri: string | undefined,
  values: Record<string, unknown>
): void {
  const key = resourceUri ?? "__global";
  const prev = mossConfigByScope.get(key) ?? {};
  mossConfigByScope.set(key, { ...prev, ...values });
}

function mergedMossConfig(resource?: { toString(): string }): Record<string, unknown> {
  const g = mossConfigByScope.get("__global") ?? {};
  if (!resource) return { ...g };
  const s = mossConfigByScope.get(resource.toString()) ?? {};
  return { ...g, ...s };
}

export const workspace = {
  getConfiguration(section: string, resource?: { toString(): string }) {
    if (section !== "moss") {
      return { get: () => undefined };
    }
    const data = mergedMossConfig(resource);
    return {
      get: <T>(key: string) => data[key] as T,
    };
  },
};

export interface WorkspaceFolder {
  readonly uri: URI;
  readonly name: string;
  readonly index: number;
}

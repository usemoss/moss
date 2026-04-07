import * as vscode from "vscode";

export const MOSS_SECRET_KEY_PROJECT_KEY = "moss.projectKey";

/** When true, Moss output includes extra indexing / spike / search detail (Phase 8). */
export function getMossLogVerbose(): boolean {
  return vscode.workspace.getConfiguration("moss").get<boolean>("logVerbose") === true;
}

/** Default hybrid-search blend (semantic-heavy), aligned with Moss SDK defaults. */
export const DEFAULT_QUERY_ALPHA = 0.8;

export interface ResolvedConfig {
  projectId: string | undefined;
  projectKey: string | undefined;
  indexName: string;
  modelId: string;
  includeGlobs: string[];
  excludeGlobs: string[];
  maxFileSizeBytes: number;
  topK: number;
  /** Hybrid search: 1.0 = semantic only, 0.0 = keyword only; clamped to [0, 1]. */
  alpha: number;
  chunkMaxLines: number;
  chunkOverlapLines: number;
  workspaceFolder: vscode.WorkspaceFolder;
}

/** Parse `moss.alpha`: finite number in [0, 1], else default. */
export function resolveQueryAlpha(raw: unknown): number {
  const n = typeof raw === "number" ? raw : Number(raw);
  if (!Number.isFinite(n)) return DEFAULT_QUERY_ALPHA;
  return Math.min(1, Math.max(0, n));
}

function toStringArray(value: unknown, fallback: string[]): string[] {
  if (Array.isArray(value)) {
    return value.filter((x): x is string => typeof x === "string" && x.length > 0);
  }
  if (typeof value === "string" && value.trim() !== "") {
    return [value.trim()];
  }
  return fallback;
}

function sanitizeIndexNameSegment(name: string): string {
  const s = name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40);
  return s.length > 0 ? s : "workspace";
}

/** Default index name when `moss.indexName` is empty: `vscode-moss-<sanitized-folder-name>`. */
export function defaultIndexNameForFolder(folder: vscode.WorkspaceFolder): string {
  return `vscode-moss-${sanitizeIndexNameSegment(folder.name)}`;
}

/**
 * Project key precedence: SecretStorage → `moss.projectKey` → `MOSS_PROJECT_KEY`.
 */
export async function resolveProjectKey(
  secrets: vscode.SecretStorage,
  cfg: vscode.WorkspaceConfiguration
): Promise<string | undefined> {
  const fromSecret = await secrets.get(MOSS_SECRET_KEY_PROJECT_KEY);
  if (fromSecret?.trim()) return fromSecret.trim();

  const fromCfg = cfg.get<string>("projectKey")?.trim();
  if (fromCfg) return fromCfg;

  const fromEnv = process.env.MOSS_PROJECT_KEY?.trim();
  if (fromEnv) return fromEnv;

  return undefined;
}

function resolveProjectId(cfg: vscode.WorkspaceConfiguration): string | undefined {
  const fromCfg = cfg.get<string>("projectId")?.trim();
  if (fromCfg) return fromCfg;
  return process.env.MOSS_PROJECT_ID?.trim();
}

/**
 * Global Moss credentials (unscoped config), same precedence as Phase 0.
 */
export async function resolveCredentials(
  context: vscode.ExtensionContext
): Promise<{ projectId: string; projectKey: string } | undefined> {
  const cfg = vscode.workspace.getConfiguration("moss");
  const projectId = resolveProjectId(cfg);
  if (!projectId) return undefined;

  const projectKey = await resolveProjectKey(context.secrets, cfg);
  if (!projectKey) return undefined;

  return { projectId, projectKey };
}

/**
 * Moss settings + credentials for one workspace folder (`moss.*` scoped to that folder's URI).
 */
export async function getMossConfig(
  secrets: vscode.SecretStorage,
  folder: vscode.WorkspaceFolder
): Promise<ResolvedConfig> {
  const cfg = vscode.workspace.getConfiguration("moss", folder.uri);

  const projectId = resolveProjectId(cfg);
  const projectKey = await resolveProjectKey(secrets, cfg);

  const configuredIndex = cfg.get<string>("indexName")?.trim();
  const indexName =
    configuredIndex && configuredIndex.length > 0
      ? configuredIndex
      : defaultIndexNameForFolder(folder);

  const modelId = cfg.get<string>("modelId")?.trim() || "moss-minilm";

  const includeGlobs = toStringArray(cfg.get("includeGlob"), ["**/*"]);
  const defaultExcludes = [
    "**/node_modules/**",
    "**/.git/**",
    "**/dist/**",
    "**/out/**",
    "**/.next/**",
    "**/build/**",
  ];
  const excludeGlobs = toStringArray(cfg.get("excludeGlob"), defaultExcludes);

  const maxFileSizeBytes = cfg.get<number>("maxFileSizeBytes") ?? 1_048_576;
  const topK = cfg.get<number>("topK") ?? 10;
  const alpha = resolveQueryAlpha(cfg.get("alpha"));

  const chunkMaxLines = cfg.get<number>("chunkMaxLines") ?? 100;
  const chunkOverlapLines = cfg.get<number>("chunkOverlapLines") ?? 12;

  return {
    projectId,
    projectKey,
    indexName,
    modelId,
    includeGlobs,
    excludeGlobs,
    maxFileSizeBytes,
    topK,
    alpha,
    chunkMaxLines,
    chunkOverlapLines,
    workspaceFolder: folder,
  };
}

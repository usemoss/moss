import { createHash } from "node:crypto";
import * as vscode from "vscode";

/** Legacy global SecretStorage key for project key only (pre–workspace blobs). Used for migration + fallback. */
export const MOSS_LEGACY_GLOBAL_PROJECT_KEY = "moss.projectKey";

/** @deprecated Use {@link MOSS_LEGACY_GLOBAL_PROJECT_KEY}. */
export const MOSS_SECRET_KEY_PROJECT_KEY = MOSS_LEGACY_GLOBAL_PROJECT_KEY;

const MOSS_CREDENTIALS_SECRET_PREFIX = "moss.credentials.v1";

/** When true, Moss output includes extra indexing / spike / search detail (Phase 8). */
export function getMossLogVerbose(): boolean {
  return vscode.workspace.getConfiguration("moss").get<boolean>("logVerbose") === true;
}

/** Default hybrid-search blend (semantic-heavy), aligned with Moss SDK defaults. */
export const DEFAULT_QUERY_ALPHA = 0.8;

const DEFAULT_MAX_FILE_SIZE_BYTES = 1_048_576;
const MAX_FILE_SIZE_BYTES_CAP = 50 * 1024 * 1024;
const DEFAULT_TOP_K = 10;
const TOP_K_CAP = 100;
const DEFAULT_CHUNK_MAX_LINES = 100;
const CHUNK_MAX_LINES_CAP = 10_000;
const DEFAULT_CHUNK_OVERLAP_LINES = 12;
const CHUNK_OVERLAP_CAP = 10_000;

function clampPositiveInt(
  value: unknown,
  fallback: number,
  max: number
): number {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return fallback;
  const i = Math.trunc(n);
  if (i < 1) return fallback;
  return Math.min(i, max);
}

function clampNonNegativeInt(
  value: unknown,
  fallback: number,
  max: number
): number {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return fallback;
  const i = Math.trunc(n);
  if (i < 0) return fallback;
  return Math.min(i, max);
}

function clampMaxFileSizeBytes(value: unknown): number {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return DEFAULT_MAX_FILE_SIZE_BYTES;
  const i = Math.trunc(n);
  if (i < 1024) return DEFAULT_MAX_FILE_SIZE_BYTES;
  return Math.min(i, MAX_FILE_SIZE_BYTES_CAP);
}

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
  /** When true, paths matching the workspace folder root `.gitignore` are excluded from indexing. */
  respectGitignore: boolean;
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
 * Stable SecretStorage key for this workspace folder’s Moss credentials JSON blob.
 */
export function workspaceCredentialsSecretKey(folder: vscode.WorkspaceFolder): string {
  const digest = createHash("sha256").update(folder.uri.toString()).digest("hex");
  return `${MOSS_CREDENTIALS_SECRET_PREFIX}.${digest}`;
}

export interface MossCredentialsPayload {
  projectId: string;
  projectKey: string;
}

function parseCredentialsBlob(raw: string): MossCredentialsPayload | undefined {
  try {
    const data: unknown = JSON.parse(raw);
    if (typeof data !== "object" || data === null || Array.isArray(data)) return undefined;
    const rec = data as Record<string, unknown>;
    const projectId =
      typeof rec.projectId === "string" ? rec.projectId.trim() : "";
    const projectKey =
      typeof rec.projectKey === "string" ? rec.projectKey.trim() : "";
    if (!projectId || !projectKey) return undefined;
    return { projectId, projectKey };
  } catch {
    return undefined;
  }
}

export async function readCredentialsBlob(
  secrets: vscode.SecretStorage,
  folder: vscode.WorkspaceFolder
): Promise<MossCredentialsPayload | undefined> {
  const raw = await secrets.get(workspaceCredentialsSecretKey(folder));
  if (!raw) return undefined;
  return parseCredentialsBlob(raw);
}

export async function storeCredentialsForWorkspace(
  secrets: vscode.SecretStorage,
  folder: vscode.WorkspaceFolder,
  creds: MossCredentialsPayload
): Promise<void> {
  const payload: MossCredentialsPayload = {
    projectId: creds.projectId.trim(),
    projectKey: creds.projectKey.trim(),
  };
  await secrets.store(
    workspaceCredentialsSecretKey(folder),
    JSON.stringify(payload)
  );
}

export async function deleteCredentialsForWorkspace(
  secrets: vscode.SecretStorage,
  folder: vscode.WorkspaceFolder
): Promise<void> {
  await secrets.delete(workspaceCredentialsSecretKey(folder));
}

function resolveProjectIdFromEnv(): string | undefined {
  return process.env.MOSS_PROJECT_ID?.trim();
}

/**
 * Fallback when no workspace credentials blob exists: legacy global SecretStorage entry
 * (see {@link MOSS_LEGACY_GLOBAL_PROJECT_KEY}) → `MOSS_PROJECT_KEY`.
 * Project ID / key are not read from `settings.json` — use the configure command or env.
 */
export async function resolveProjectKey(
  secrets: vscode.SecretStorage
): Promise<string | undefined> {
  const fromLegacy = await secrets.get(MOSS_LEGACY_GLOBAL_PROJECT_KEY);
  if (fromLegacy?.trim()) return fromLegacy.trim();

  const fromEnv = process.env.MOSS_PROJECT_KEY?.trim();
  if (fromEnv) return fromEnv;

  return undefined;
}

/**
 * Moss credentials for one workspace folder. Precedence:
 * 1. Workspace credentials blob (SecretStorage, per folder URI)
 * 2. Environment pair: both `MOSS_PROJECT_ID` and `MOSS_PROJECT_KEY`
 * 3. Migration: legacy global project-key secret + `MOSS_PROJECT_ID` → persisted as workspace blob
 * 4. Assemble `MOSS_PROJECT_ID` (env) + {@link resolveProjectKey} (legacy secret or `MOSS_PROJECT_KEY`)
 */
export async function resolveCredentialsForWorkspace(
  secrets: vscode.SecretStorage,
  folder: vscode.WorkspaceFolder
): Promise<MossCredentialsPayload | undefined> {
  const fromBlob = await readCredentialsBlob(secrets, folder);
  if (fromBlob) return fromBlob;

  const envId = process.env.MOSS_PROJECT_ID?.trim();
  const envKey = process.env.MOSS_PROJECT_KEY?.trim();
  if (envId && envKey) {
    return { projectId: envId, projectKey: envKey };
  }

  const projectId = resolveProjectIdFromEnv();
  const legacyGlobalKey = await secrets.get(MOSS_LEGACY_GLOBAL_PROJECT_KEY);
  if (projectId && legacyGlobalKey?.trim()) {
    const migrated: MossCredentialsPayload = {
      projectId,
      projectKey: legacyGlobalKey.trim(),
    };
    await storeCredentialsForWorkspace(secrets, folder, migrated);
    return migrated;
  }

  if (!projectId) return undefined;

  const projectKey = await resolveProjectKey(secrets);
  if (!projectKey) return undefined;

  return { projectId, projectKey };
}

/**
 * Credentials for the first workspace folder (sidebar / search / index entry points).
 */
export async function resolveCredentials(
  context: vscode.ExtensionContext
): Promise<MossCredentialsPayload | undefined> {
  const folder = vscode.workspace.workspaceFolders?.[0];
  if (!folder) return undefined;
  return resolveCredentialsForWorkspace(context.secrets, folder);
}

/**
 * Moss settings + credentials for one workspace folder (`moss.*` scoped to that folder's URI).
 */
export async function getMossConfig(
  secrets: vscode.SecretStorage,
  folder: vscode.WorkspaceFolder
): Promise<ResolvedConfig> {
  const cfg = vscode.workspace.getConfiguration("moss", folder.uri);

  const creds = await resolveCredentialsForWorkspace(secrets, folder);

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

  const maxFileSizeBytes = clampMaxFileSizeBytes(cfg.get("maxFileSizeBytes"));
  const topK = clampPositiveInt(cfg.get("topK"), DEFAULT_TOP_K, TOP_K_CAP);
  const alpha = resolveQueryAlpha(cfg.get("alpha"));

  const chunkMaxLines = clampPositiveInt(
    cfg.get("chunkMaxLines"),
    DEFAULT_CHUNK_MAX_LINES,
    CHUNK_MAX_LINES_CAP
  );
  const chunkOverlapLines = clampNonNegativeInt(
    cfg.get("chunkOverlapLines"),
    DEFAULT_CHUNK_OVERLAP_LINES,
    CHUNK_OVERLAP_CAP
  );

  const respectGitignoreRaw = cfg.get<boolean | undefined>("respectGitignore");
  const respectGitignore = respectGitignoreRaw !== false;

  return {
    projectId: creds?.projectId,
    projectKey: creds?.projectKey,
    indexName,
    modelId,
    includeGlobs,
    excludeGlobs,
    maxFileSizeBytes,
    topK,
    alpha,
    chunkMaxLines,
    chunkOverlapLines,
    respectGitignore,
    workspaceFolder: folder,
  };
}

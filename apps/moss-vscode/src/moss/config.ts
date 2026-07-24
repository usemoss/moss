import * as crypto from "node:crypto";
import * as fs from "node:fs";
import * as path from "node:path";
import * as vscode from "vscode";
import { config as loadDotenv } from "dotenv";

const SECRET_PROJECT_ID = "moss.projectId";
const SECRET_PROJECT_KEY = "moss.projectKey";

export interface MossCredentials {
  projectId: string;
  projectKey: string;
}

function loadEnvFile(): void {
  const candidates = [
    path.join(__dirname, "..", ".env"),
    path.join(__dirname, "..", "..", ".env"),
  ];
  for (const envPath of candidates) {
    if (fs.existsSync(envPath)) {
      loadDotenv({ path: envPath, quiet: true });
      return;
    }
  }
}

export async function resolveCredentials(
  context: vscode.ExtensionContext,
): Promise<MossCredentials | undefined> {
  loadEnvFile();

  const config = vscode.workspace.getConfiguration("moss");
  const fromSettingsId = (config.get<string>("projectId") ?? "").trim();
  const fromSettingsKey = (config.get<string>("projectKey") ?? "").trim();

  const fromSecretsId = (await context.secrets.get(SECRET_PROJECT_ID)) ?? "";
  const fromSecretsKey = (await context.secrets.get(SECRET_PROJECT_KEY)) ?? "";

  const fromEnvId = (process.env.MOSS_PROJECT_ID ?? "").trim();
  const fromEnvKey = (process.env.MOSS_PROJECT_KEY ?? "").trim();

  const projectId = fromSettingsId || fromSecretsId || fromEnvId;
  const projectKey = fromSettingsKey || fromSecretsKey || fromEnvKey;

  if (projectId && projectKey) {
    return { projectId, projectKey };
  }
  return undefined;
}

export async function promptAndStoreCredentials(
  context: vscode.ExtensionContext,
): Promise<MossCredentials | undefined> {
  const projectId = await vscode.window.showInputBox({
    title: "Moss Project ID",
    prompt: "Enter your Moss project ID",
    ignoreFocusOut: true,
  });
  if (!projectId?.trim()) {
    return undefined;
  }

  const projectKey = await vscode.window.showInputBox({
    title: "Moss Project Key",
    prompt: "Enter your Moss project key",
    password: true,
    ignoreFocusOut: true,
  });
  if (!projectKey?.trim()) {
    return undefined;
  }

  return storeCredentials(context, projectId.trim(), projectKey.trim());
}

export async function storeCredentials(
  context: vscode.ExtensionContext,
  projectId: string,
  projectKey?: string,
): Promise<MossCredentials | undefined> {
  const id = projectId.trim();
  if (!id) {
    return undefined;
  }

  const keyInput = projectKey?.trim();
  let key = keyInput;
  if (!key) {
    const existing = await resolveCredentials(context);
    if (existing?.projectId === id) {
      key = existing.projectKey;
    }
  }
  if (!key) {
    return undefined;
  }

  await context.secrets.store(SECRET_PROJECT_ID, id);
  if (keyInput) {
    await context.secrets.store(SECRET_PROJECT_KEY, keyInput);
  }
  return { projectId: id, projectKey: key };
}

export interface MossSettingsSnapshot {
  projectId: string;
  hasProjectKey: boolean;
  credentialsConfigured: boolean;
  cloudSync: boolean;
}

export async function getSettingsSnapshot(
  context: vscode.ExtensionContext,
): Promise<MossSettingsSnapshot> {
  const credentials = await resolveCredentials(context);
  const fromSecretsId = (await context.secrets.get(SECRET_PROJECT_ID)) ?? "";
  const fromSecretsKey = (await context.secrets.get(SECRET_PROJECT_KEY)) ?? "";

  return {
    projectId: fromSecretsId || credentials?.projectId || "",
    hasProjectKey: !!fromSecretsKey || !!credentials?.projectKey,
    credentialsConfigured: !!credentials,
    cloudSync: isCloudSyncEnabled(),
  };
}

export async function setCloudSyncEnabled(enabled: boolean): Promise<void> {
  await vscode.workspace
    .getConfiguration("moss")
    .update("cloudSync", enabled, vscode.ConfigurationTarget.Global);
}

export function workspaceSessionName(): string {
  const folders = vscode.workspace.workspaceFolders;
  const root =
    folders?.[0]?.uri.fsPath ??
    vscode.workspace.name ??
    "default-workspace";
  const hash = crypto.createHash("sha256").update(root).digest("hex").slice(0, 12);
  return `vscode-${hash}`;
}

export function indexedStateKey(): string {
  return `moss.indexed.${workspaceSessionName()}`;
}

export async function markWorkspaceIndexed(
  context: vscode.ExtensionContext,
): Promise<void> {
  await context.workspaceState.update(indexedStateKey(), true);
}

export function isWorkspaceMarkedIndexed(
  context: vscode.ExtensionContext,
): boolean {
  return context.workspaceState.get(indexedStateKey(), false);
}

export async function clearWorkspaceIndexed(
  context: vscode.ExtensionContext,
): Promise<void> {
  await context.workspaceState.update(indexedStateKey(), undefined);
}

export function getSearchOptions(): { topK: number; alpha: number } {
  const config = vscode.workspace.getConfiguration("moss");
  return {
    topK: config.get<number>("topK", 20),
    alpha: config.get<number>("alpha", 0.7),
  };
}

export function isCloudSyncEnabled(): boolean {
  return vscode.workspace.getConfiguration("moss").get<boolean>("cloudSync", true);
}

export function getIncludeGlobs(): string[] {
  return vscode.workspace
    .getConfiguration("moss")
    .get<string[]>("includeGlobs", [
      "**/*.{ts,tsx,js,jsx,mjs,cjs,py,go,rs,md,json,yaml,yml,java,kt,swift,rb,php,cs,cpp,c,h,hpp}",
    ]);
}

export function getExcludeGlobs(): string[] {
  return vscode.workspace
    .getConfiguration("moss")
    .get<string[]>("excludeGlobs", [
      "**/node_modules/**",
      "**/.git/**",
      "**/dist/**",
      "**/build/**",
      "**/out/**",
      "**/.next/**",
      "**/coverage/**",
      "**/.venv/**",
      "**/venv/**",
      "**/target/**",
      "**/__pycache__/**",
      "**/vendor/**",
      "**/bower_components/**",
      "**/.pnpm/**",
      "**/.turbo/**",
      "**/.cache/**",
      "**/.parcel-cache/**",
      "**/Pods/**",
      "**/.gradle/**",
      "**/site-packages/**",
      "**/.pytest_cache/**",
      "**/.mypy_cache/**",
    ]);
}

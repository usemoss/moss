import { afterEach, describe, expect, it } from "vitest";
import type { SecretStorage } from "vscode";
import {
  DEFAULT_QUERY_ALPHA,
  MOSS_LEGACY_GLOBAL_PROJECT_KEY,
  defaultIndexNameForFolder,
  getMossConfig,
  getMossLogVerbose,
  resolveCredentialsForWorkspace,
  resolveProjectKey,
  resolveQueryAlpha,
  workspaceCredentialsSecretKey,
} from "../src/config.js";
import {
  resetMossTestConfig,
  setMossTestConfig,
  Uri,
  type WorkspaceFolder,
} from "./vscode-stub.js";

function memorySecrets(initial: Record<string, string> = {}): SecretStorage {
  const m = new Map<string, string>(Object.entries(initial));
  return {
    get: async (k) => m.get(k),
    store: async (k, v) => {
      m.set(k, v);
    },
    delete: async (k) => {
      m.delete(k);
    },
    onDidChange: () => ({ dispose: () => {} }),
  };
}

/** Seed workspace blob so getMossConfig resolves credentials without env. */
function secretsWithWorkspaceCreds(
  folder: WorkspaceFolder,
  projectId: string,
  projectKey: string
): SecretStorage {
  const key = workspaceCredentialsSecretKey(folder);
  return memorySecrets({
    [key]: JSON.stringify({ projectId, projectKey }),
  });
}

describe("defaultIndexNameForFolder", () => {
  it("sanitizes folder name into index segment", () => {
    const f: WorkspaceFolder = {
      uri: Uri.file("/x"),
      name: "My Cool App!!!",
      index: 0,
    };
    expect(defaultIndexNameForFolder(f)).toBe("vscode-moss-my-cool-app");
  });

  it("falls back when name sanitizes to empty", () => {
    const f: WorkspaceFolder = {
      uri: Uri.file("/x"),
      name: "@@@",
      index: 0,
    };
    expect(defaultIndexNameForFolder(f)).toBe("vscode-moss-workspace");
  });
});

describe("getMossLogVerbose", () => {
  afterEach(() => {
    resetMossTestConfig();
  });

  it("is false by default", () => {
    expect(getMossLogVerbose()).toBe(false);
  });

  it("is true when moss.logVerbose set", () => {
    setMossTestConfig(undefined, { logVerbose: true });
    expect(getMossLogVerbose()).toBe(true);
  });
});

describe("resolveProjectKey", () => {
  const prevKey = process.env.MOSS_PROJECT_KEY;

  afterEach(() => {
    resetMossTestConfig();
    if (prevKey === undefined) delete process.env.MOSS_PROJECT_KEY;
    else process.env.MOSS_PROJECT_KEY = prevKey;
  });

  it("prefers legacy global SecretStorage over MOSS_PROJECT_KEY", async () => {
    process.env.MOSS_PROJECT_KEY = "env-key";
    const secrets = memorySecrets({
      [MOSS_LEGACY_GLOBAL_PROJECT_KEY]: "secret-key",
    });
    expect(await resolveProjectKey(secrets)).toBe("secret-key");
  });

  it("uses MOSS_PROJECT_KEY when no legacy secret", async () => {
    process.env.MOSS_PROJECT_KEY = "env-only";
    const secrets = memorySecrets();
    expect(await resolveProjectKey(secrets)).toBe("env-only");
  });

  it("returns undefined when nothing set", async () => {
    delete process.env.MOSS_PROJECT_KEY;
    const secrets = memorySecrets();
    expect(await resolveProjectKey(secrets)).toBeUndefined();
  });
});

describe("resolveCredentialsForWorkspace", () => {
  const prevId = process.env.MOSS_PROJECT_ID;
  const prevKey = process.env.MOSS_PROJECT_KEY;

  afterEach(() => {
    resetMossTestConfig();
    if (prevId === undefined) delete process.env.MOSS_PROJECT_ID;
    else process.env.MOSS_PROJECT_ID = prevId;
    if (prevKey === undefined) delete process.env.MOSS_PROJECT_KEY;
    else process.env.MOSS_PROJECT_KEY = prevKey;
  });

  it("prefers workspace blob over legacy secret and env", async () => {
    process.env.MOSS_PROJECT_ID = "env-pid";
    process.env.MOSS_PROJECT_KEY = "env-pkey";
    const ws = Uri.file("/alpha");
    const folder: WorkspaceFolder = { uri: ws, name: "alpha", index: 0 };
    const blobKey = workspaceCredentialsSecretKey(folder);
    const secrets = memorySecrets({
      [blobKey]: JSON.stringify({
        projectId: "blob-pid",
        projectKey: "blob-pkey",
      }),
      [MOSS_LEGACY_GLOBAL_PROJECT_KEY]: "legacy-key",
    });
    const r = await resolveCredentialsForWorkspace(secrets, folder);
    expect(r).toEqual({ projectId: "blob-pid", projectKey: "blob-pkey" });
  });

  it("migrates legacy global key + MOSS_PROJECT_ID into workspace blob", async () => {
    delete process.env.MOSS_PROJECT_KEY;
    process.env.MOSS_PROJECT_ID = "m-pid";
    const ws = Uri.file("/migrate");
    const folder: WorkspaceFolder = { uri: ws, name: "migrate", index: 0 };
    const blobKey = workspaceCredentialsSecretKey(folder);
    const secrets = memorySecrets({
      [MOSS_LEGACY_GLOBAL_PROJECT_KEY]: "legacy-k",
    });
    const r = await resolveCredentialsForWorkspace(secrets, folder);
    expect(r).toEqual({ projectId: "m-pid", projectKey: "legacy-k" });
    const stored = await secrets.get(blobKey);
    expect(stored).toBe(
      JSON.stringify({ projectId: "m-pid", projectKey: "legacy-k" })
    );
  });

  it("uses env pair when no blob", async () => {
    process.env.MOSS_PROJECT_ID = "eid";
    process.env.MOSS_PROJECT_KEY = "ekey";
    const ws = Uri.file("/envonly");
    const folder: WorkspaceFolder = { uri: ws, name: "envonly", index: 0 };
    const secrets = memorySecrets();
    const r = await resolveCredentialsForWorkspace(secrets, folder);
    expect(r).toEqual({ projectId: "eid", projectKey: "ekey" });
  });

  it("isolates credentials by workspace folder URI", async () => {
    delete process.env.MOSS_PROJECT_ID;
    delete process.env.MOSS_PROJECT_KEY;
    const wsA = Uri.file("/proj-a");
    const wsB = Uri.file("/proj-b");
    const folderA: WorkspaceFolder = { uri: wsA, name: "a", index: 0 };
    const folderB: WorkspaceFolder = { uri: wsB, name: "b", index: 1 };
    const secrets = memorySecrets({
      [workspaceCredentialsSecretKey(folderA)]: JSON.stringify({
        projectId: "ida",
        projectKey: "ka",
      }),
      [workspaceCredentialsSecretKey(folderB)]: JSON.stringify({
        projectId: "idb",
        projectKey: "kb",
      }),
    });
    expect(await resolveCredentialsForWorkspace(secrets, folderA)).toEqual({
      projectId: "ida",
      projectKey: "ka",
    });
    expect(await resolveCredentialsForWorkspace(secrets, folderB)).toEqual({
      projectId: "idb",
      projectKey: "kb",
    });
  });
});

describe("resolveQueryAlpha", () => {
  it("defaults when missing or non-finite", () => {
    expect(resolveQueryAlpha(undefined)).toBe(DEFAULT_QUERY_ALPHA);
    expect(resolveQueryAlpha("x")).toBe(DEFAULT_QUERY_ALPHA);
    expect(resolveQueryAlpha(Number.NaN)).toBe(DEFAULT_QUERY_ALPHA);
  });

  it("clamps to 0..1", () => {
    expect(resolveQueryAlpha(-0.5)).toBe(0);
    expect(resolveQueryAlpha(1.5)).toBe(1);
    expect(resolveQueryAlpha(0)).toBe(0);
    expect(resolveQueryAlpha(1)).toBe(1);
  });

  it("passes through in-range values", () => {
    expect(resolveQueryAlpha(0.5)).toBe(0.5);
    expect(resolveQueryAlpha(0.8)).toBe(0.8);
  });
});

describe("getMossConfig", () => {
  afterEach(() => {
    resetMossTestConfig();
  });

  it("uses configured index name when set", async () => {
    const ws = Uri.file("/repo");
    setMossTestConfig(ws.toString(), {
      indexName: "my-custom-index",
    });
    const folder: WorkspaceFolder = { uri: ws, name: "repo", index: 0 };
    const secrets = secretsWithWorkspaceCreds(folder, "pid", "pk");
    const c = await getMossConfig(secrets, folder);
    expect(c.indexName).toBe("my-custom-index");
    expect(c.topK).toBe(10);
    expect(c.alpha).toBe(DEFAULT_QUERY_ALPHA);
  });

  it("uses configured alpha when set", async () => {
    const ws = Uri.file("/repo");
    setMossTestConfig(ws.toString(), {
      alpha: 0.35,
    });
    const folder: WorkspaceFolder = { uri: ws, name: "repo", index: 0 };
    const secrets = secretsWithWorkspaceCreds(folder, "pid", "pk");
    const c = await getMossConfig(secrets, folder);
    expect(c.alpha).toBe(0.35);
  });

  it("defaults index name from folder when indexName empty", async () => {
    const ws = Uri.file("/repo");
    setMossTestConfig(ws.toString(), {
      indexName: "",
    });
    const folder: WorkspaceFolder = { uri: ws, name: "alpha-beta", index: 0 };
    const secrets = secretsWithWorkspaceCreds(folder, "p", "k");
    const c = await getMossConfig(secrets, folder);
    expect(c.indexName).toBe("vscode-moss-alpha-beta");
  });

  it("defaults respectGitignore to true when unset", async () => {
    const ws = Uri.file("/repo");
    setMossTestConfig(ws.toString(), {});
    const folder: WorkspaceFolder = { uri: ws, name: "r", index: 0 };
    const secrets = secretsWithWorkspaceCreds(folder, "p", "k");
    const c = await getMossConfig(secrets, folder);
    expect(c.respectGitignore).toBe(true);
  });

  it("respectGitignore false when configured", async () => {
    const ws = Uri.file("/repo");
    setMossTestConfig(ws.toString(), {
      respectGitignore: false,
    });
    const folder: WorkspaceFolder = { uri: ws, name: "r", index: 0 };
    const secrets = secretsWithWorkspaceCreds(folder, "p", "k");
    const c = await getMossConfig(secrets, folder);
    expect(c.respectGitignore).toBe(false);
  });

  it("clamps invalid numeric settings to safe defaults or caps", async () => {
    const ws = Uri.file("/repo");
    setMossTestConfig(ws.toString(), {
      maxFileSizeBytes: -1,
      topK: 9999,
      chunkMaxLines: 0,
      chunkOverlapLines: -5,
    });
    const folder: WorkspaceFolder = { uri: ws, name: "r", index: 0 };
    const secrets = secretsWithWorkspaceCreds(folder, "p", "k");
    const c = await getMossConfig(secrets, folder);
    expect(c.maxFileSizeBytes).toBe(1_048_576);
    expect(c.topK).toBe(100);
    expect(c.chunkMaxLines).toBe(100);
    expect(c.chunkOverlapLines).toBe(12);
  });
});

import { afterEach, describe, expect, it } from "vitest";
import type { SecretStorage, WorkspaceConfiguration } from "vscode";
import {
  DEFAULT_QUERY_ALPHA,
  MOSS_SECRET_KEY_PROJECT_KEY,
  defaultIndexNameForFolder,
  getMossConfig,
  getMossLogVerbose,
  resolveProjectKey,
  resolveQueryAlpha,
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

function cfgFrom(values: Record<string, unknown>): WorkspaceConfiguration {
  return {
    get: <T>(key: string) => values[key] as T,
    has: () => false,
    inspect: () => undefined,
    update: async () => undefined,
  };
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

  it("prefers SecretStorage over settings and env", async () => {
    process.env.MOSS_PROJECT_KEY = "env-key";
    const secrets = memorySecrets({ [MOSS_SECRET_KEY_PROJECT_KEY]: "secret-key" });
    const cfg = cfgFrom({ projectKey: "cfg-key" });
    expect(await resolveProjectKey(secrets, cfg)).toBe("secret-key");
  });

  it("uses settings when no secret", async () => {
    const secrets = memorySecrets();
    const cfg = cfgFrom({ projectKey: "cfg-key" });
    expect(await resolveProjectKey(secrets, cfg)).toBe("cfg-key");
  });

  it("uses MOSS_PROJECT_KEY when no secret or cfg", async () => {
    process.env.MOSS_PROJECT_KEY = "env-only";
    const secrets = memorySecrets();
    const cfg = cfgFrom({});
    expect(await resolveProjectKey(secrets, cfg)).toBe("env-only");
  });

  it("returns undefined when nothing set", async () => {
    delete process.env.MOSS_PROJECT_KEY;
    const secrets = memorySecrets();
    const cfg = cfgFrom({});
    expect(await resolveProjectKey(secrets, cfg)).toBeUndefined();
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
      projectId: "pid",
      projectKey: "pk",
    });
    const folder: WorkspaceFolder = { uri: ws, name: "repo", index: 0 };
    const c = await getMossConfig(memorySecrets(), folder);
    expect(c.indexName).toBe("my-custom-index");
    expect(c.topK).toBe(10);
    expect(c.alpha).toBe(DEFAULT_QUERY_ALPHA);
  });

  it("uses configured alpha when set", async () => {
    const ws = Uri.file("/repo");
    setMossTestConfig(ws.toString(), {
      projectId: "pid",
      projectKey: "pk",
      alpha: 0.35,
    });
    const folder: WorkspaceFolder = { uri: ws, name: "repo", index: 0 };
    const c = await getMossConfig(memorySecrets(), folder);
    expect(c.alpha).toBe(0.35);
  });

  it("defaults index name from folder when indexName empty", async () => {
    const ws = Uri.file("/repo");
    setMossTestConfig(ws.toString(), {
      indexName: "",
      projectId: "p",
      projectKey: "k",
    });
    const folder: WorkspaceFolder = { uri: ws, name: "alpha-beta", index: 0 };
    const c = await getMossConfig(memorySecrets(), folder);
    expect(c.indexName).toBe("vscode-moss-alpha-beta");
  });

  it("defaults respectGitignore to true when unset", async () => {
    const ws = Uri.file("/repo");
    setMossTestConfig(ws.toString(), {
      projectId: "p",
      projectKey: "k",
    });
    const folder: WorkspaceFolder = { uri: ws, name: "r", index: 0 };
    const c = await getMossConfig(memorySecrets(), folder);
    expect(c.respectGitignore).toBe(true);
  });

  it("respectGitignore false when configured", async () => {
    const ws = Uri.file("/repo");
    setMossTestConfig(ws.toString(), {
      projectId: "p",
      projectKey: "k",
      respectGitignore: false,
    });
    const folder: WorkspaceFolder = { uri: ws, name: "r", index: 0 };
    const c = await getMossConfig(memorySecrets(), folder);
    expect(c.respectGitignore).toBe(false);
  });

  it("clamps invalid numeric settings to safe defaults or caps", async () => {
    const ws = Uri.file("/repo");
    setMossTestConfig(ws.toString(), {
      projectId: "p",
      projectKey: "k",
      maxFileSizeBytes: -1,
      topK: 9999,
      chunkMaxLines: 0,
      chunkOverlapLines: -5,
    });
    const folder: WorkspaceFolder = { uri: ws, name: "r", index: 0 };
    const c = await getMossConfig(memorySecrets(), folder);
    expect(c.maxFileSizeBytes).toBe(1_048_576);
    expect(c.topK).toBe(100);
    expect(c.chunkMaxLines).toBe(100);
    expect(c.chunkOverlapLines).toBe(12);
  });
});

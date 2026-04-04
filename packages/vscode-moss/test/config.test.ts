import { afterEach, describe, expect, it } from "vitest";
import type { SecretStorage, WorkspaceConfiguration } from "vscode";
import {
  MOSS_SECRET_KEY_PROJECT_KEY,
  defaultIndexNameForFolder,
  getMossConfig,
  getMossLogVerbose,
  resolveProjectKey,
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
    expect(c.queryMode).toBe("local");
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

  it("treats queryMode cloud only when exactly cloud", async () => {
    const ws = Uri.file("/r");
    setMossTestConfig(ws.toString(), {
      projectId: "p",
      projectKey: "k",
      queryMode: "cloud",
    });
    const folder: WorkspaceFolder = { uri: ws, name: "r", index: 0 };
    const c = await getMossConfig(memorySecrets(), folder);
    expect(c.queryMode).toBe("cloud");
  });
});

import { fork, spawnSync, type ChildProcess } from "node:child_process";
import * as fs from "node:fs";
import * as path from "node:path";
import * as vscode from "vscode";
import type {
  DocumentInfo,
  GetDocumentsOptions,
  MutationOptions,
  PushIndexResult,
  QueryOptions,
  SearchResult,
} from "@moss-dev/moss";
import type { MossCredentials } from "./config";
import { workspaceSessionName } from "./config";

type WorkerResponse =
  | { id: number; ok: true; result: unknown }
  | { id: number; ok: false; error: string };

export interface LocalMossSession {
  readonly docCount: number;
  addDocs(
    docs: DocumentInfo[],
    options?: MutationOptions,
  ): Promise<{ added: number; updated: number }>;
  deleteDocs(docIds: string[]): Promise<number>;
  query(query: string, options?: QueryOptions): Promise<SearchResult>;
  getDocs(options?: GetDocumentsOptions): Promise<DocumentInfo[]>;
  loadIndex(indexName: string): Promise<number>;
  pushIndex(): Promise<PushIndexResult>;
  saveToDisk(cachePath: string): Promise<void>;
  loadFromDisk(cachePath: string): Promise<number>;
}

export class MossSessionManager {
  private worker: ChildProcess | undefined;
  private session: WorkerBackedSession | undefined;
  private ready = false;
  private nextId = 1;
  private pending = new Map<
    number,
    { resolve: (value: unknown) => void; reject: (err: Error) => void }
  >();

  constructor(
    private readonly extensionPath: string,
    private readonly log: (message: string) => void = () => undefined,
  ) {}

  get isReady(): boolean {
    return this.ready && !!this.session;
  }

  getSession(): LocalMossSession {
    if (!this.session) {
      throw new Error("Moss session is not initialized");
    }
    return this.session;
  }

  async initialize(credentials: MossCredentials): Promise<LocalMossSession> {
    this.ready = false;
    this.ensureWorker();
    const name = workspaceSessionName();
    const result = await this.call<{ docCount: number }>("initialize", {
      projectId: credentials.projectId,
      projectKey: credentials.projectKey,
      name,
      modelId: "moss-minilm",
    });
    this.session = new WorkerBackedSession(
      result.docCount,
      (method, args) => this.call(method, args),
    );
    this.ready = true;
    return this.session;
  }

  dispose(): void {
    this.ready = false;
    this.session = undefined;
    for (const { reject } of this.pending.values()) {
      reject(new Error("Moss worker was disposed"));
    }
    this.pending.clear();
    this.worker?.kill();
    this.worker = undefined;
  }

  private ensureWorker(): void {
    if (this.worker && !this.worker.killed) {
      return;
    }

    const workerPath = path.join(this.extensionPath, "dist", "mossWorker.js");
    const execPath = findNodeBinary(this.log);
    this.log(`Starting Moss worker: ${workerPath}`);
    this.log(`Moss worker execPath: ${execPath}`);
    this.worker = fork(workerPath, [], {
      stdio: ["ignore", "pipe", "pipe", "ipc"],
      execPath,
      env: {
        ...process.env,
        ELECTRON_RUN_AS_NODE: "1",
      },
    });

    this.worker.stdout?.on("data", (chunk: Buffer) => {
      this.log(`[worker] ${chunk.toString().trimEnd()}`);
    });
    this.worker.stderr?.on("data", (chunk: Buffer) => {
      this.log(`[worker:stderr] ${chunk.toString().trimEnd()}`);
    });
    this.worker.on("message", (message: WorkerResponse) => {
      const pending = this.pending.get(message.id);
      if (!pending) {
        return;
      }
      this.pending.delete(message.id);
      if (message.ok) {
        pending.resolve(message.result);
      } else {
        pending.reject(new Error(message.error));
      }
    });
    this.worker.on("exit", (code, signal) => {
      const detail = `Moss worker exited (code=${code ?? "null"}, signal=${signal ?? "null"})`;
      this.log(detail);
      this.ready = false;
      this.session = undefined;
      this.worker = undefined;
      for (const { reject } of this.pending.values()) {
        reject(new Error(`${detail}. The native Moss runtime may have crashed.`));
      }
      this.pending.clear();
    });
    this.worker.on("error", (err) => {
      this.log(`Moss worker error: ${err.message}`);
      for (const { reject } of this.pending.values()) {
        reject(err);
      }
      this.pending.clear();
    });
  }

  private call<T>(method: string, args: unknown): Promise<T> {
    this.ensureWorker();
    const worker = this.worker;
    if (!worker || !worker.connected) {
      return Promise.reject(new Error("Moss worker is not connected"));
    }
    const id = this.nextId++;
    return new Promise<T>((resolve, reject) => {
      this.pending.set(id, {
        resolve: (value) => resolve(value as T),
        reject,
      });
      worker.send({ id, method, args }, (err) => {
        if (!err) {
          return;
        }
        this.pending.delete(id);
        reject(err);
      });
    });
  }
}

function findSystemNode(): string | undefined {
  try {
    if (process.platform === "win32") {
      const result = spawnSync("where", ["node"], { encoding: "utf8", shell: true });
      const line = result.stdout
        ?.split(/\r?\n/)
        .map((entry) => entry.trim())
        .find(Boolean);
      return line || undefined;
    }
    const result = spawnSync("which", ["node"], { encoding: "utf8" });
    const line = result.stdout?.trim();
    return line || undefined;
  } catch {
    return undefined;
  }
}

function isExecutable(filePath: string): boolean {
  try {
    return fs.existsSync(filePath);
  } catch {
    return false;
  }
}

/**
 * Minimum Node.js the packaged `@moss-dev/moss` (1.4.1) supports at runtime.
 * The wrapper declares `engines.node: ">=20.4"`; the worker must run on a Node
 * that meets that floor, so binary selection verifies the version rather than
 * only that a binary exists.
 */
export const MIN_WORKER_NODE_VERSION = "20.4.0";

export function parseNodeVersion(
  raw: string | undefined,
): { major: number; minor: number; patch: number } | undefined {
  if (!raw) {
    return undefined;
  }
  const match = /(\d+)\.(\d+)\.(\d+)/.exec(raw.trim());
  if (!match) {
    return undefined;
  }
  return { major: Number(match[1]), minor: Number(match[2]), patch: Number(match[3]) };
}

export function nodeMeetsWorkerFloor(raw: string | undefined): boolean {
  const version = parseNodeVersion(raw);
  if (!version) {
    return false;
  }
  const [minMajor, minMinor, minPatch] = MIN_WORKER_NODE_VERSION.split(".").map(Number);
  if (version.major !== minMajor) {
    return version.major > minMajor;
  }
  if (version.minor !== minMinor) {
    return version.minor > minMinor;
  }
  return version.patch >= minPatch;
}

/**
 * Resolve a candidate's runtime Node version. Runs the binary with
 * `ELECTRON_RUN_AS_NODE=1` so that VS Code's embedded Electron reports the
 * Node version it bundles (not the Electron version), matching how the worker
 * is forked.
 */
function nodeBinaryVersion(candidate: string): string | undefined {
  try {
    const result = spawnSync(candidate, ["-e", "process.stdout.write(process.versions.node)"], {
      encoding: "utf8",
      env: { ...process.env, ELECTRON_RUN_AS_NODE: "1" },
      timeout: 5000,
    });
    if (result.status !== 0) {
      return undefined;
    }
    return result.stdout?.trim() || undefined;
  } catch {
    return undefined;
  }
}

function findNodeBinary(log: (message: string) => void = () => undefined): string {
  const fromSetting = vscode.workspace.getConfiguration("moss").get<string>("nodePath")?.trim();

  const candidates = [
    fromSetting,
    process.env.NODE_BINARY,
    process.env.npm_node_execpath,
    findSystemNode(),
    process.env.npm_execpath?.endsWith("npm-cli.js")
      ? path.join(path.dirname(path.dirname(process.env.npm_execpath)), "bin", "node")
      : undefined,
    process.platform === "win32" ? "C:\\Program Files\\nodejs\\node.exe" : undefined,
    "/opt/homebrew/bin/node",
    "/usr/local/bin/node",
    "/usr/bin/node",
    process.execPath,
  ].filter(Boolean) as string[];

  let tooOld: { candidate: string; version: string } | undefined;
  for (const candidate of candidates) {
    if (!isExecutable(candidate)) {
      continue;
    }
    const version = nodeBinaryVersion(candidate);
    if (!nodeMeetsWorkerFloor(version)) {
      if (version) {
        tooOld = { candidate, version };
      }
      continue;
    }
    if (candidate === process.execPath) {
      log(
        `Moss worker using VS Code embedded Node ${version} (set moss.nodePath for a standalone Node ${MIN_WORKER_NODE_VERSION}+ binary if needed)`,
      );
    }
    return candidate;
  }

  const detail = tooOld
    ? ` The closest match, ${tooOld.candidate}, is Node ${tooOld.version}, below the required ${MIN_WORKER_NODE_VERSION} (@moss-dev/moss 1.4.1).`
    : "";
  throw new Error(
    `Could not find a Node.js ${MIN_WORKER_NODE_VERSION}+ binary for the Moss worker.${detail} Install Node ${MIN_WORKER_NODE_VERSION}+ or set moss.nodePath.`,
  );
}

class WorkerBackedSession implements LocalMossSession {
  constructor(
    private count: number,
    private readonly call: <T>(method: string, args: unknown) => Promise<T>,
  ) {}

  get docCount(): number {
    return this.count;
  }

  async addDocs(
    docs: DocumentInfo[],
    options?: MutationOptions,
  ): Promise<{ added: number; updated: number }> {
    const result = await this.call<{ added: number; updated: number; docCount: number }>(
      "addDocs",
      { docs, options },
    );
    this.count = result.docCount;
    return { added: result.added, updated: result.updated };
  }

  async deleteDocs(docIds: string[]): Promise<number> {
    const result = await this.call<{ deleted: number; docCount: number }>("deleteDocs", {
      docIds,
    });
    this.count = result.docCount;
    return result.deleted;
  }

  async query(query: string, options?: QueryOptions): Promise<SearchResult> {
    return this.call<SearchResult>("query", { query, options });
  }

  async getDocs(options?: GetDocumentsOptions): Promise<DocumentInfo[]> {
    const result = await this.call<{ docs: DocumentInfo[]; docCount: number }>("getDocs", {
      options,
    });
    this.count = result.docCount;
    return result.docs;
  }

  async loadIndex(indexName: string): Promise<number> {
    const result = await this.call<{ loaded: number; docCount: number }>("loadIndex", {
      indexName,
    });
    this.count = result.docCount;
    return result.loaded;
  }

  async pushIndex(): Promise<PushIndexResult> {
    const result = await this.call<PushIndexResult & { docCount: number }>("pushIndex", {});
    this.count = result.docCount;
    return result;
  }

  async saveToDisk(cachePath: string): Promise<void> {
    const result = await this.call<{ docCount: number }>("saveToDisk", { cachePath });
    this.count = result.docCount;
  }

  async loadFromDisk(cachePath: string): Promise<number> {
    const result = await this.call<{ loaded: number; docCount: number }>("loadFromDisk", {
      cachePath,
    });
    this.count = result.docCount;
    return result.loaded;
  }
}

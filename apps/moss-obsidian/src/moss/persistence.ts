import * as crypto from "crypto";
import * as fs from "fs";
import * as fsp from "fs/promises";
import * as path from "path";
import type { DocumentInfo } from "@moss-dev/moss";

export interface IndexMeta {
  vaultPath: string;
  sessionName: string;
  model: string;
  files: number;
  chunks: number;
  pathChunkCounts: Record<string, number>;
  /** Modification time (ms) of each note when it was indexed. */
  pathMtimes?: Record<string, number>;
  savedAt: string;
  cloudPushedAt?: string;
}

/**
 * Stable session / cloud index name for a vault: `obsidian-<sha256(name)[:12]>`.
 * Derived from the vault's NAME (not its absolute path) so the same synced
 * vault resolves to the same cloud index on every device.
 */
export function vaultSessionName(vaultName: string): string {
  const hash = crypto.createHash("sha256").update(vaultName).digest("hex").slice(0, 12);
  return `obsidian-${hash}`;
}

export function pathChunkCountsFromDocs(docs: DocumentInfo[]): Record<string, number> {
  const counts = new Map<string, number>();
  for (const doc of docs) {
    const filePath = doc.metadata?.filePath;
    if (filePath) {
      counts.set(filePath, (counts.get(filePath) ?? 0) + 1);
    }
  }
  return Object.fromEntries(counts);
}

export class IndexCache {
  constructor(private readonly cacheDir: string) {}

  get dir(): string {
    return this.cacheDir;
  }

  get metaPath(): string {
    return path.join(this.cacheDir, "meta.json");
  }

  exists(): boolean {
    return fs.existsSync(this.metaPath);
  }

  async ensureDir(): Promise<string> {
    await fsp.mkdir(this.cacheDir, { recursive: true });
    return this.cacheDir;
  }

  async readMeta(): Promise<IndexMeta | undefined> {
    try {
      const raw = await fsp.readFile(this.metaPath, "utf8");
      const parsed = JSON.parse(raw) as IndexMeta;
      if (
        !parsed ||
        typeof parsed.vaultPath !== "string" ||
        typeof parsed.sessionName !== "string" ||
        typeof parsed.pathChunkCounts !== "object" ||
        parsed.pathChunkCounts === null
      ) {
        return undefined;
      }
      return parsed;
    } catch {
      return undefined;
    }
  }

  async writeMeta(meta: IndexMeta): Promise<void> {
    await this.ensureDir();
    const tmp = `${this.metaPath}.tmp`;
    await fsp.writeFile(tmp, JSON.stringify(meta, null, 2), "utf8");
    await fsp.rename(tmp, this.metaPath);
  }

  async clear(): Promise<void> {
    try {
      await fsp.rm(this.cacheDir, { recursive: true, force: true });
    } catch {
      // ignore
    }
  }
}

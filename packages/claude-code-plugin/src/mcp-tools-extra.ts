import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import * as fs from "node:fs";
import * as path from "node:path";
import { execFileSync } from "node:child_process";
import { chunkFile, hashContent, type Manifest } from "./lib/chunker.js";

const DEFAULT_EXTENSIONS = ["ts", "tsx", "js", "jsx", "py", "rs", "go", "java", "md", "json", "yaml", "yml"];
const DEFAULT_IGNORE = ["node_modules", "dist", ".git", ".next", "__pycache__", "target", "build", ".venv"];
const SKIP_FILES = ["package-lock.json", "yarn.lock", "pnpm-lock.yaml", ".min.js", ".min.css", ".bundle.js"];
const BATCH_SIZE = 100;

interface SyncClients {
  projectId: string;
  projectKey: string;
}

function manifestPath(indexName: string): string {
  const dataDir = process.env.CLAUDE_PLUGIN_DATA || "/tmp/claude-moss";
  return path.join(dataDir, "manifests", `${indexName}.json`);
}

function loadManifest(indexName: string): Manifest {
  try {
    const p = manifestPath(indexName);
    if (fs.existsSync(p)) return JSON.parse(fs.readFileSync(p, "utf-8"));
  } catch { /* fresh start */ }
  return {};
}

function saveManifest(indexName: string, manifest: Manifest): void {
  const p = manifestPath(indexName);
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, JSON.stringify(manifest, null, 2));
}

function shouldSkip(filePath: string): boolean {
  return SKIP_FILES.some((p) => filePath.includes(p));
}

function getTrackedFiles(dir: string): string[] {
  try {
    const output = execFileSync("git", ["ls-files"], { cwd: dir, encoding: "utf-8" });
    return output.trim().split("\n").filter(Boolean);
  } catch {
    // Not a git repo — walk directory manually
    const files: string[] = [];
    function walk(d: string, prefix: string) {
      for (const entry of fs.readdirSync(d, { withFileTypes: true })) {
        const rel = prefix ? `${prefix}/${entry.name}` : entry.name;
        if (entry.isDirectory()) {
          if (!DEFAULT_IGNORE.includes(entry.name)) walk(path.join(d, entry.name), rel);
        } else {
          files.push(rel);
        }
      }
    }
    walk(dir, "");
    return files;
  }
}

export function registerExtraTools(server: McpServer, clients: SyncClients): void {
  server.tool(
    "sync_project",
    "Incrementally sync local files to a Moss index. Uses content hashes to detect changes — only re-indexes modified, added, or deleted files. Much faster than full re-index.",
    {
      dir: z.string().default(".").describe("Directory to sync (default: current working directory)"),
      indexName: z.string().describe("Moss index name to sync to"),
      extensions: z
        .array(z.string())
        .default(DEFAULT_EXTENSIONS)
        .describe("File extensions to include"),
      ignore: z
        .array(z.string())
        .default(DEFAULT_IGNORE)
        .describe("Directory names to ignore"),
    },
    async (args) => {
      const dir = path.resolve(args.dir);
      if (!fs.existsSync(dir)) {
        return { content: [{ type: "text", text: `Error: directory not found: ${dir}` }], isError: true };
      }

      const extSet = new Set(args.extensions);
      const manifest = loadManifest(args.indexName);
      const newManifest: Manifest = {};

      const files = getTrackedFiles(dir).filter((f) => {
        const ext = f.split(".").pop() || "";
        return extSet.has(ext) && !shouldSkip(f);
      });

      const added: string[] = [];
      const modified: string[] = [];
      const deleted: string[] = [];
      const unchanged: string[] = [];

      const allNewChunks: Array<{ id: string; text: string; metadata: Record<string, string> }> = [];
      const allDeleteIds: string[] = [];

      for (const relPath of files) {
        const absPath = path.join(dir, relPath);
        let content: string;
        try {
          const stat = fs.statSync(absPath);
          if (stat.size === 0 || stat.size > 500_000) continue;
          content = fs.readFileSync(absPath, "utf-8");
        } catch {
          continue;
        }

        const hash = hashContent(content);
        const prev = manifest[relPath];

        if (prev && prev.hash === hash) {
          unchanged.push(relPath);
          newManifest[relPath] = prev;
          continue;
        }

        if (prev) {
          modified.push(relPath);
          allDeleteIds.push(...prev.chunkIds);
        } else {
          added.push(relPath);
        }

        const chunks = chunkFile(relPath, content);
        allNewChunks.push(...chunks);
        newManifest[relPath] = { hash, chunkIds: chunks.map((c) => c.id) };
      }

      for (const prevPath of Object.keys(manifest)) {
        if (!newManifest[prevPath]) {
          deleted.push(prevPath);
          allDeleteIds.push(...manifest[prevPath].chunkIds);
        }
      }

      // Apply via REST
      const { cloudAddDocs, cloudDeleteDocs, cloudCreateIndex, cloudListIndexes } = await import("./lib/moss-rest.js");
      const creds = { projectId: clients.projectId, projectKey: clients.projectKey };

      let indexExists = false;
      try {
        const indexes = (await cloudListIndexes(creds)) as Array<{ name: string }>;
        indexExists = indexes.some((idx) => idx.name === args.indexName);
      } catch { /* assume doesn't exist */ }

      // Delete old chunks
      if (allDeleteIds.length > 0 && indexExists) {
        for (let i = 0; i < allDeleteIds.length; i += BATCH_SIZE) {
          try {
            await cloudDeleteDocs({ ...creds, indexName: args.indexName, docIds: allDeleteIds.slice(i, i + BATCH_SIZE) });
          } catch { /* best-effort */ }
        }
      }

      // Upload new chunks
      if (allNewChunks.length > 0) {
        if (!indexExists) {
          await cloudCreateIndex({ ...creds, indexName: args.indexName, docs: allNewChunks.slice(0, BATCH_SIZE) });
          for (let i = BATCH_SIZE; i < allNewChunks.length; i += BATCH_SIZE) {
            await cloudAddDocs({ ...creds, indexName: args.indexName, docs: allNewChunks.slice(i, i + BATCH_SIZE) });
          }
        } else {
          for (let i = 0; i < allNewChunks.length; i += BATCH_SIZE) {
            await cloudAddDocs({ ...creds, indexName: args.indexName, docs: allNewChunks.slice(i, i + BATCH_SIZE) });
          }
        }
      }

      saveManifest(args.indexName, newManifest);

      const summary = [
        `Sync complete for index "${args.indexName}":`,
        `  Files scanned: ${files.length}`,
        `  Added: ${added.length} files`,
        `  Modified: ${modified.length} files`,
        `  Deleted: ${deleted.length} files`,
        `  Unchanged: ${unchanged.length} files`,
        `  Chunks uploaded: ${allNewChunks.length}`,
        `  Chunks removed: ${allDeleteIds.length}`,
      ].join("\n");

      return { content: [{ type: "text", text: summary }] };
    }
  );
}

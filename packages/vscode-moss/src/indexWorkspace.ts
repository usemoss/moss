import * as vscode from "vscode";
import path from "node:path";
import { MossClient } from "@moss-dev/moss";
import { getMossConfig, resolveCredentials } from "./config.js";
import { chunkFileContent } from "./chunking.js";
import { formatError } from "./formatError.js";
import {
  MOSS_LAST_INDEXED_KEY,
  type LastIndexedState,
} from "./lastIndexed.js";
import { mossLog } from "./mossLog.js";
import { ensureLocalIndexLoaded, notifySearchIndexStale } from "./mossQueryState.js";
import { notifyMossIndexed } from "./mossStatusBar.js";
import type { DocumentInfo } from "@moss-dev/moss";

const MAX_FILE_SCAN = 80_000;
const MAX_MOSS_DOCUMENTS = 60_000;
const POST_CREATE_SETTLE_MS = 2500;

/** Always applied on top of `moss.excludeGlob` (Phase 5 merge with safe defaults). */
const EXTRA_SAFE_EXCLUDES = [
  "**/.svn/**",
  "**/.hg/**",
  "**/__pycache__/**",
];

/** VS Code–style language id for structure-aware chunking (Markdown, JS/TS, and other Tree-sitter grammars). */
function languageIdFromPath(fsPath: string): string | undefined {
  switch (path.extname(fsPath).toLowerCase()) {
    case ".md":
    case ".mdx":
      return "markdown";
    case ".ts":
    case ".mts":
    case ".cts":
      return "typescript";
    case ".tsx":
      return "typescriptreact";
    case ".js":
    case ".mjs":
    case ".cjs":
      return "javascript";
    case ".jsx":
      return "javascriptreact";
    case ".py":
    case ".pyi":
    case ".pyw":
      return "python";
    case ".rs":
      return "rust";
    case ".go":
      return "go";
    case ".java":
      return "java";
    case ".rb":
    case ".rake":
    case ".ru":
      return "ruby";
    case ".php":
      return "php";
    case ".c":
    case ".h":
      return "c";
    case ".cpp":
    case ".cc":
    case ".cxx":
    case ".hpp":
    case ".hh":
    case ".hxx":
    case ".inl":
    case ".cu":
      return "cpp";
    case ".cs":
      return "csharp";
    default:
      return undefined;
  }
}

const BINARY_EXT = new Set(
  [
    ".zip",
    ".tar",
    ".gz",
    ".tgz",
    ".rar",
    ".7z",
    ".bz2",
    ".xz",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".bmp",
    ".tif",
    ".tiff",
    ".heic",
    ".pdf",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".wasm",
    ".mp3",
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".webm",
    ".wmv",
    ".bin",
    ".sqlite",
    ".sqlite3",
    ".db",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".otf",
    ".class",
    ".jar",
    ".pyc",
    ".pyo",
    ".o",
    ".a",
    ".lib",
    ".obj",
    ".ilk",
    ".pdb",
    ".dmg",
    ".iso",
    ".img",
  ].map((e) => e.toLowerCase())
);

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function uniqueSorted(values: string[]): string[] {
  return [...new Set(values.filter(Boolean))].sort((a, b) => a.localeCompare(b));
}

function toBraceGlob(patterns: string[]): string {
  const u = uniqueSorted(patterns);
  if (u.length === 0) return "**/*";
  if (u.length === 1) return u[0]!;
  return `{${u.join(",")}}`;
}

function canBraceCombine(patterns: string[]): boolean {
  return patterns.every((p) => !/[{}]/.test(p) && !p.includes(","));
}

async function tolerateDeleteIndex(
  client: MossClient,
  indexName: string,
  log: vscode.OutputChannel
): Promise<void> {
  try {
    await client.deleteIndex(indexName);
    mossLog(
      log,
      `Moss: Deleted existing index "${indexName}" (if it existed).`,
      "verbose"
    );
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    if (/not found|does not exist/i.test(msg)) {
      mossLog(
        log,
        `Moss: No existing index "${indexName}" to delete (ok).`,
        "verbose"
      );
    } else {
      mossLog(log, `Moss: deleteIndex warning: ${msg}`);
    }
  }
}

function isBinaryExt(fsPath: string): boolean {
  return BINARY_EXT.has(path.extname(fsPath).toLowerCase());
}

async function findWorkspaceFiles(
  includeGlobs: string[],
  excludeGlobs: string[],
  maxFiles: number,
  token: vscode.CancellationToken
): Promise<{ uris: vscode.Uri[]; scanTruncated: boolean }> {
  const includes = uniqueSorted(includeGlobs.length > 0 ? includeGlobs : ["**/*"]);
  const excludePat =
    excludeGlobs.length > 0 ? toBraceGlob(uniqueSorted(excludeGlobs)) : null;

  const dedupe = new Set<string>();
  const out: vscode.Uri[] = [];

  const addBatch = (batch: readonly vscode.Uri[]) => {
    for (const u of batch) {
      const k = u.toString();
      if (dedupe.has(k)) continue;
      dedupe.add(k);
      out.push(u);
    }
  };

  if (includes.length === 1) {
    const batch = await vscode.workspace.findFiles(
      includes[0]!,
      excludePat,
      maxFiles + 1,
      token
    );
    addBatch(batch);
  } else if (canBraceCombine(includes)) {
    const batch = await vscode.workspace.findFiles(
      `{${includes.join(",")}}`,
      excludePat,
      maxFiles + 1,
      token
    );
    addBatch(batch);
  } else {
    for (const inc of includes) {
      if (token.isCancellationRequested) break;
      const batch = await vscode.workspace.findFiles(
        inc,
        excludePat,
        maxFiles + 1 - out.length,
        token
      );
      addBatch(batch);
      if (out.length > maxFiles) break;
    }
  }

  const scanTruncated = out.length > maxFiles;
  return { uris: out.slice(0, maxFiles), scanTruncated };
}

async function readUtf8Text(uri: vscode.Uri): Promise<string | undefined> {
  try {
    const bytes = await vscode.workspace.fs.readFile(uri);
    if (bytes.includes(0)) return undefined;
    const dec = new TextDecoder("utf-8", { fatal: true });
    return dec.decode(bytes);
  } catch {
    return undefined;
  }
}

/**
 * Full workspace reindex: discover files, chunk, REST deleteIndex + createIndex, optional loadIndex.
 */
export async function runIndexWorkspace(
  context: vscode.ExtensionContext,
  log: vscode.OutputChannel
): Promise<void> {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders?.length) {
    void vscode.window.showErrorMessage(
      "Moss: Open a folder or workspace before indexing."
    );
    return;
  }

  const creds = await resolveCredentials(context);
  if (!creds) {
    void vscode.window.showErrorMessage(
      "Moss: Missing credentials. Run “Moss: Configure credentials” or set MOSS_PROJECT_ID / MOSS_PROJECT_KEY."
    );
    return;
  }

  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "Moss: Indexing workspace",
      cancellable: true,
    },
    async (progress, token) => {
      mossLog(log, "Moss: Index workspace — starting…");

      const primary = folders[0]!;
      const cfg = await getMossConfig(context.secrets, primary);

      const excludeGlobs = uniqueSorted([
        ...EXTRA_SAFE_EXCLUDES,
        ...cfg.excludeGlobs,
      ]);

      progress.report({ message: "Scanning files…" });
      mossLog(log, "Moss: Scanning workspace for files…");
      const { uris, scanTruncated } = await findWorkspaceFiles(
        cfg.includeGlobs,
        excludeGlobs,
        MAX_FILE_SCAN,
        token
      );

      if (token.isCancellationRequested) {
        mossLog(log, "Moss: Indexing cancelled (after scan).");
        return;
      }

      if (scanTruncated) {
        const msg = `File scan stopped at ${MAX_FILE_SCAN} files. Narrow moss.includeGlob or add moss.excludeGlob to index a smaller set.`;
        mossLog(log, msg);
        void vscode.window.showWarningMessage(`Moss: ${msg}`);
      }

      mossLog(log, `Moss: Found ${uris.length} file(s) to consider.`, "verbose");
      mossLog(
        log,
        `Moss: Reading and chunking ${uris.length} file(s) — progress is shown in the notification…`
      );

      uris.sort((a, b) => a.fsPath.localeCompare(b.fsPath));

      const allDocs: DocumentInfo[] = [];
      let filesIndexed = 0;
      let skippedSize = 0;
      let skippedBinary = 0;
      let skippedDecode = 0;
      let decodeLogged = false;

      const total = uris.length;
      for (let i = 0; i < uris.length; i++) {
        if (token.isCancellationRequested) {
          mossLog(log, "Moss: Indexing cancelled while reading files.");
          return;
        }

        const uri = uris[i]!;
        progress.report({
          message: `Reading files (${i + 1}/${total})…`,
          increment: total > 0 ? 100 / total : 0,
        });

        const folder = vscode.workspace.getWorkspaceFolder(uri);
        if (!folder) continue;

        const folderIndex = folders.indexOf(folder);
        if (folderIndex < 0) continue;

        if (isBinaryExt(uri.fsPath)) {
          skippedBinary += 1;
          continue;
        }

        let stat: vscode.FileStat;
        try {
          stat = await vscode.workspace.fs.stat(uri);
        } catch {
          continue;
        }

        if (stat.size > cfg.maxFileSizeBytes) {
          skippedSize += 1;
          continue;
        }

        const text = await readUtf8Text(uri);

        if (text === undefined) {
          skippedDecode += 1;
          if (!decodeLogged) {
            mossLog(
              log,
              "Moss: One or more files were skipped (invalid UTF-8 or binary content).",
              "verbose"
            );
            decodeLogged = true;
          }
          continue;
        }

        const relativePath = vscode.workspace.asRelativePath(uri, false);
        if (relativePath === "") continue;

        const chunks = await chunkFileContent(
          relativePath,
          text,
          {
            chunkMaxLines: cfg.chunkMaxLines,
            chunkOverlapLines: cfg.chunkOverlapLines,
            workspaceFolderIndex: folderIndex,
            workspaceFolderName: folder.name,
            chunkIdNamespace:
              folders.length > 1 ? String(folderIndex) : undefined,
          },
          languageIdFromPath(uri.fsPath)
        );

        allDocs.push(...chunks);
        filesIndexed += 1;

        if (allDocs.length >= MAX_MOSS_DOCUMENTS) {
          mossLog(
            log,
            `Moss: Chunk limit reached (${MAX_MOSS_DOCUMENTS}); remaining files are skipped.`
          );
          void vscode.window.showWarningMessage(
            `Moss: Index truncated at ${MAX_MOSS_DOCUMENTS} chunks. Narrow include patterns or raise the limit in code.`
          );
          break;
        }
      }

      if (token.isCancellationRequested) {
        mossLog(log, "Moss: Indexing cancelled before upload.");
        return;
      }

      if (allDocs.length === 0) {
        const msg =
          "No indexable documents were produced (empty workspace, filters, or unsupported files).";
        mossLog(log, msg);
        void vscode.window.showWarningMessage(`Moss: ${msg}`);
        return;
      }

      progress.report({ message: "Uploading index to Moss…", increment: 0 });
      mossLog(
        log,
        `Moss: Uploading ${allDocs.length} chunk(s) to Moss (createIndex)…`
      );

      const client = new MossClient(creds.projectId, creds.projectKey);

      try {
        await tolerateDeleteIndex(client, cfg.indexName, log);
        if (token.isCancellationRequested) {
          mossLog(log, "Moss: Indexing cancelled before createIndex.");
          return;
        }

        await client.createIndex(cfg.indexName, allDocs, {
          modelId: cfg.modelId,
        });
        notifySearchIndexStale();
        mossLog(
          log,
          `Moss: createIndex finished — ${allDocs.length} chunks from ${filesIndexed} file(s), index “${cfg.indexName}”.`
        );
      } catch (e: unknown) {
        const msg = formatError(e);
        mossLog(log, `Moss: createIndex failed: ${msg}`);
        void vscode.window.showErrorMessage(`Moss: Indexing failed: ${msg}`);
        return;
      }

      await context.workspaceState.update(MOSS_LAST_INDEXED_KEY, {
        indexName: cfg.indexName,
        docCount: allDocs.length,
        fileCount: filesIndexed,
        timestamp: Date.now(),
      } satisfies LastIndexedState);

      notifyMossIndexed();

      mossLog(
        log,
        `Moss: Skipped while scanning — ${skippedSize} over size cap, ${skippedBinary} binary/ext, ${skippedDecode} decode/binary.`,
        "verbose"
      );

      progress.report({ message: "Preparing local search cache…" });
      await sleep(POST_CREATE_SETTLE_MS);
      if (token.isCancellationRequested) {
        void vscode.window.showInformationMessage(
          "Moss: Index uploaded. Local cache warm-up was cancelled."
        );
        return;
      }
      try {
        const localState: { loadedIndexName?: string } = {};
        await ensureLocalIndexLoaded(client, cfg.indexName, localState);
        mossLog(
          log,
          "Moss: loadIndex completed (local query cache warmed).",
          "verbose"
        );
      } catch (e: unknown) {
        mossLog(
          log,
          `Moss: loadIndex after indexing failed (search will use cloud fallback): ${formatError(e)}`
        );
      }

      void vscode.window.showInformationMessage(
        `Moss: Indexed ${filesIndexed} file(s) → ${allDocs.length} chunk(s) (“${cfg.indexName}”).`
      );
    }
  );
}

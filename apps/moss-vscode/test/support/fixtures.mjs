// Deterministic, seeded, privacy-safe session-cache fixtures.
//
// A valid baseline cache is produced once by the REAL installed native addon
// (`saveToDisk`) using synthetic, seeded custom embeddings — no customer data,
// no network, no embedding model. Each corruption is a deterministic mutation
// of a fresh copy of that baseline, reproducing the torn/corrupt on-disk shapes
// that must yield a catchable JS error rather than aborting the process.
//
// Fixtures are generated into a temp directory at test time and never committed,
// so they cannot leak into the packaged VSIX.

import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { pathToFileURL } from "node:url";
import { SESSION_NAME, EMBED_DIM, STUB_PROJECT_ID } from "./env.mjs";

/** Deterministic pseudo-random embedding for a given seed (LCG, no Math.random). */
function seededEmbedding(seed) {
  const v = new Array(EMBED_DIM);
  let x = (seed * 2654435761) >>> 0;
  for (let i = 0; i < EMBED_DIM; i++) {
    x = (1103515245 * x + 12345) >>> 0;
    v[i] = ((x % 2000) / 1000) - 1; // in [-1, 1)
  }
  return v;
}

/** The seeded, privacy-safe document corpus (synthetic text only). */
export const SEED_DOCS = [
  { id: "doc-1", text: "alpha regression fixture", embedding: seededEmbedding(1) },
  { id: "doc-2", text: "bravo regression fixture", embedding: seededEmbedding(2) },
  { id: "doc-3", text: "charlie regression fixture", embedding: seededEmbedding(3) },
];

/** In-process custom authenticator — resolves a synthetic token, no network. */
function localAuthenticator() {
  return {
    async getAuthToken() {
      return { token: "local-fixture-token", expiresIn: 3600 };
    },
    async getAuthHeader() {
      return "Bearer local-fixture-token";
    },
  };
}

/**
 * Build a valid baseline cache at `<cacheRoot>/<SESSION_NAME>/` using the real
 * addon. Uses the custom-authenticator bridge + `modelId: "custom"` so the whole
 * operation is offline and model-free. Returns the session directory path.
 */
export async function buildBaselineCache(cacheRoot) {
  const { MossClient } = await import("@moss-dev/moss");
  return buildBaselineWith(cacheRoot, MossClient);
}

/**
 * Same as buildBaselineCache but loads the SDK from a specific install dir
 * (e.g. the SDK bundled inside an extracted VSIX), so the fixture and the worker
 * exercise the identical packaged native addon.
 */
export async function buildBaselineCacheWith(cacheRoot, sdkDir) {
  const pkg = JSON.parse(fs.readFileSync(path.join(sdkDir, "package.json"), "utf8"));
  const entry = path.join(sdkDir, pkg.main ?? "dist/index.esm.js");
  const { MossClient } = await import(pathToFileURL(entry).href);
  return buildBaselineWith(cacheRoot, MossClient);
}

async function buildBaselineWith(cacheRoot, MossClient) {
  fs.rmSync(cacheRoot, { recursive: true, force: true });
  fs.mkdirSync(cacheRoot, { recursive: true });
  const client = new MossClient(STUB_PROJECT_ID, localAuthenticator());
  const session = await client.session(SESSION_NAME, "custom");
  await session.addDocs(SEED_DOCS);
  await session.saveToDisk(cacheRoot);
  await session.close?.();
  await client.close?.();

  const dir = path.join(cacheRoot, SESSION_NAME);
  const files = fs.readdirSync(dir).sort();
  const expected = ["docs.json", "index.mossvec", "session.json"];
  for (const f of expected) {
    if (!files.includes(f)) {
      throw new Error(`baseline cache missing ${f}; got ${files.join(", ")}`);
    }
  }
  return dir;
}

/**
 * The corruption catalog. Each entry mutates a session directory in place to
 * produce one torn/corrupt shape. All are deterministic given the baseline.
 */
export const CORRUPTIONS = {
  // .mossvec header claims N vectors but only 1 vector's bytes are present.
  // The 304-byte header is fixed-size; truncate to header + one vector.
  torn_vector_count: (dir) => {
    const p = path.join(dir, "index.mossvec");
    const buf = fs.readFileSync(p);
    const headerLen = buf.length - SEED_DOCS.length * EMBED_DIM * 4;
    fs.writeFileSync(p, buf.subarray(0, headerLen + 1 * EMBED_DIM * 4));
  },
  // Vector data truncated mid-entry (last vector cut short).
  truncated_mid_vector: (dir) => {
    const p = path.join(dir, "index.mossvec");
    const buf = fs.readFileSync(p);
    fs.writeFileSync(p, buf.subarray(0, buf.length - 10));
  },
  // Empty sidecar (interrupted write before any bytes).
  empty_vector_file: (dir) => {
    fs.writeFileSync(path.join(dir, "index.mossvec"), Buffer.alloc(0));
  },
  // Corrupt magic bytes.
  bad_magic: (dir) => {
    const p = path.join(dir, "index.mossvec");
    const buf = fs.readFileSync(p);
    buf.write("XXXX", 0, "utf8");
    fs.writeFileSync(p, buf);
  },
  // Required sidecar missing entirely.
  missing_vector_file: (dir) => {
    fs.rmSync(path.join(dir, "index.mossvec"));
  },
  // Metadata/vector count mismatch (session.json claims fewer docIds).
  docids_count_mismatch: (dir) => {
    const p = path.join(dir, "session.json");
    const meta = JSON.parse(fs.readFileSync(p, "utf8"));
    meta.docIds = meta.docIds.slice(0, meta.docIds.length - 1);
    fs.writeFileSync(p, JSON.stringify(meta));
  },
  // Malformed JSON in docs.json.
  invalid_docs_json: (dir) => {
    fs.writeFileSync(path.join(dir, "docs.json"), "{ this is not valid json");
  },
};

/**
 * Materialize one corrupt cache. Copies the baseline session dir into a fresh
 * `<destRoot>/<SESSION_NAME>/` and applies the named corruption. Returns
 * `destRoot` (the cachePath passed to loadFromDisk).
 */
export function makeCorruptCache(baselineDir, destRoot, corruptionName) {
  const mutate = CORRUPTIONS[corruptionName];
  if (!mutate) throw new Error(`unknown corruption: ${corruptionName}`);
  const destDir = path.join(destRoot, SESSION_NAME);
  fs.rmSync(destRoot, { recursive: true, force: true });
  fs.mkdirSync(destDir, { recursive: true });
  for (const f of fs.readdirSync(baselineDir)) {
    fs.copyFileSync(path.join(baselineDir, f), path.join(destDir, f));
  }
  mutate(destDir);
  return destRoot;
}

/** Create an isolated temp root for fixtures under the OS temp dir. */
export function makeTempRoot(label) {
  return fs.mkdtempSync(path.join(os.tmpdir(), `moss-vscode-${label}-`));
}

/**
 * Best-effort recursive remove. A live worker memory-maps `index.mossvec`, and
 * Windows refuses to unlink a mapped file (EPERM) until the worker exits — the
 * lingering temp dir is harmless and the OS reclaims it, so cleanup failures are
 * ignored. Never used for assertions.
 */
export function safeRm(target) {
  try {
    fs.rmSync(target, { recursive: true, force: true });
  } catch {
    // ignore — see doc comment (Windows mmap/EPERM); temp dir is ephemeral.
  }
}

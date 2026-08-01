// Shared, hermetic environment setup for the Moss VS Code regression suite.
//
// The regression gate is deliberately offline and deterministic:
//   * MOSS_DISABLE_TELEMETRY=1     — no telemetry network calls.
//   * MOSS_MODEL_CACHE_DIR=<tmp>   — an isolated, empty model cache so a stray
//     model load can never silently reach the public model host; the gate uses
//     `modelId: "custom"` which loads no embedding model at all.
//   * MOSS_AUTH_URL / MOSS_INDEX_URL are pointed at a loopback auth stub by the
//     worker-survival test (see support/authStub.mjs) so credential validation
//     in the native addon never leaves the machine.
//
// The crash boundary under test — `SessionIndex.loadFromDisk` deserializing a
// torn on-disk cache — lives in the native addon's format/validation code and is
// independent of the embedding model. Exercising it with `custom` embeddings
// therefore drives the identical native deserialize path the shipped
// `moss-minilm` sessions use, while keeping CI fully hermetic.

import * as os from "node:os";
import * as path from "node:path";
import * as fs from "node:fs";

/** Session name shared by the fixture generator and the worker initializer. */
export const SESSION_NAME = "vscode-regression-session";

/** Embedding dimension for the seeded custom-embedding fixtures. */
export const EMBED_DIM = 16;

/** Deterministic project credentials — never real, never network-bound. */
export const STUB_PROJECT_ID = "local-regression-project";
export const STUB_PROJECT_KEY = "local-regression-key";

/**
 * Apply the hermetic environment to `process.env` (or a copy). Returns the
 * model-cache directory so callers can assert it stayed empty (no download).
 */
export function applyHermeticEnv(env = process.env) {
  env.MOSS_DISABLE_TELEMETRY = "1";
  const modelCache = fs.mkdtempSync(path.join(os.tmpdir(), "moss-vscode-modelcache-"));
  env.MOSS_MODEL_CACHE_DIR = modelCache;
  return modelCache;
}

/** Build the env object passed to a forked worker (mirrors client.ts). */
export function workerEnv(extra = {}) {
  return {
    ...process.env,
    ELECTRON_RUN_AS_NODE: "1",
    MOSS_DISABLE_TELEMETRY: "1",
    ...extra,
  };
}

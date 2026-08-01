// Bundles the REAL supervisor (src/moss/client.ts) for use in a Node test
// process by aliasing the `vscode` host to test/support/vscodeStub.mjs. This
// lets the negative-control test assert the shipped MossSessionManager's
// crash-handling behavior directly, with no production changes — the same
// esbuild toolchain the extension already builds with.

import * as esbuild from "esbuild";
import * as os from "node:os";
import * as path from "node:path";
import * as fs from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";

const SUPPORT_DIR = path.dirname(fileURLToPath(import.meta.url));
const APP_ROOT = path.resolve(SUPPORT_DIR, "..", "..");

let cached;

/** Bundle + import client.ts once; returns its module exports (MossSessionManager, ...). */
export async function loadSupervisorModule() {
  if (cached) return cached;
  const outfile = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "moss-vscode-supervisor-")), "client.mjs");
  await esbuild.build({
    entryPoints: [path.join(APP_ROOT, "src", "moss", "client.ts")],
    absWorkingDir: APP_ROOT,
    bundle: true,
    outfile,
    format: "esm",
    platform: "node",
    target: "node20",
    // Keep the native SDK external (loaded by the forked worker, not here).
    external: ["@moss-dev/moss", "@moss-dev/moss-core"],
    alias: { vscode: path.join(SUPPORT_DIR, "vscodeStub.mjs") },
    // Provide a real require() so bundled CJS deps (e.g. dotenv) can load node
    // builtins under ESM output.
    banner: {
      js: "import { createRequire as __cr } from 'node:module'; const require = __cr(import.meta.url);",
    },
    logLevel: "silent",
  });
  cached = await import(pathToFileURL(outfile).href);
  return cached;
}

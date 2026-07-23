// VSIX integrity gate (MOS-166).
//
// Presence checks alone are insufficient. This packages nothing itself — it
// verifies the already-built .vsix by extracting it and asserting:
//   1. the bundled wrapper/core/platform versions are exactly the fixed pinned
//      set (@moss-dev/moss 1.4.1 -> @moss-dev/moss-core 0.20.1 for all five
//      platform packages), and the app lockfile has not dropped below it;
//   2. no test source, fixtures, or hidden test-hook / debug exports leaked into
//      the package (in the JS wrapper, the worker bundle, or the native addon);
//   3. the extracted worker, run against the VSIX's OWN bundled .node, returns a
//      catchable IPC error on a torn cache and stays alive — i.e. the packaged
//      artifact actually ships the fixed crash boundary.

import { execSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, mkdtempSync, rmSync } from "node:fs";
import * as os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const extensionRoot = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");

const FIXED_WRAPPER = "1.4.1";
const FIXED_CORE = "0.20.1";
const PLATFORM_PACKAGES = [
  "@moss-dev/moss-core-darwin-arm64",
  "@moss-dev/moss-core-darwin-x64",
  "@moss-dev/moss-core-linux-arm64-gnu",
  "@moss-dev/moss-core-linux-x64-gnu",
  "@moss-dev/moss-core-win32-x64-msvc",
];

function fail(msg) {
  console.error(`✗ ${msg}`);
  process.exit(1);
}

function parseVersion(v) {
  return v.split("-")[0].split(".").map((n) => parseInt(n, 10));
}
// Returns true if `a` >= `b` (major.minor.patch).
function gte(a, b) {
  const [a0, a1, a2] = parseVersion(a);
  const [b0, b1, b2] = parseVersion(b);
  if (a0 !== b0) return a0 > b0;
  if (a1 !== b1) return a1 > b1;
  return a2 >= b2;
}

// ---------------------------------------------------------------------------
// 0. Lockfile floor: packaging must fail if the app lock drops below the fix.
// ---------------------------------------------------------------------------
const lock = JSON.parse(readFileSync(path.join(extensionRoot, "package-lock.json"), "utf8"));
const lockWrapper = lock.packages?.["node_modules/@moss-dev/moss"]?.version;
const lockCore = lock.packages?.["node_modules/@moss-dev/moss-core"]?.version;
if (!lockWrapper || !gte(lockWrapper, FIXED_WRAPPER)) {
  fail(`lockfile @moss-dev/moss is ${lockWrapper}, below fixed floor ${FIXED_WRAPPER}`);
}
if (!lockCore || !gte(lockCore, FIXED_CORE)) {
  fail(`lockfile @moss-dev/moss-core is ${lockCore}, below fixed floor ${FIXED_CORE}`);
}
for (const pkg of PLATFORM_PACKAGES) {
  const v = lock.packages?.[`node_modules/${pkg}`]?.version;
  if (v !== lockCore) {
    fail(`lockfile platform package ${pkg} is ${v}, expected same core version ${lockCore}`);
  }
}
console.log(`✓ lockfile pins @moss-dev/moss ${lockWrapper} -> moss-core ${lockCore} (all platforms)`);

// ---------------------------------------------------------------------------
// 1. Locate + extract the VSIX.
// ---------------------------------------------------------------------------
const vsixFiles = readdirSync(extensionRoot).filter((n) => n.endsWith(".vsix"));
if (!vsixFiles.length) fail("no .vsix file found — run `npm run package` first");
const vsix = path.join(extensionRoot, vsixFiles.sort().at(-1));

const listing = execSync(`unzip -Z1 "${vsix}"`, { encoding: "utf8" }).split(/\r?\n/).filter(Boolean);

// ---------------------------------------------------------------------------
// 2. Reject leaks: no test source, fixtures, promo, logs, or TS source.
// ---------------------------------------------------------------------------
const leakRules = [
  { re: /^extension\/test\//, what: "test source/fixtures" },
  { re: /\.test\.mjs$/, what: "test file" },
  { re: /^extension\/src\//, what: "TypeScript source" },
  { re: /\.tsx?$/, what: "TypeScript source" },
  // Source maps embed the original TypeScript via `sourcesContent`, so shipping
  // them would leak the very source the rules above reject.
  { re: /\.map$/, what: "source map (embeds TypeScript source)" },
  { re: /^extension\/promo\//, what: "promo project" },
  { re: /\.log$/, what: "log file" },
  { re: /^extension\/scripts\//, what: "build/verify scripts" },
];
const leaks = listing.filter((entry) => leakRules.some((r) => r.re.test(entry)));
if (leaks.length) {
  for (const l of leaks.slice(0, 20)) console.error(`   leaked: ${l}`);
  fail(`${leaks.length} disallowed file(s) leaked into the VSIX`);
}
console.log("✓ no test source, fixtures, promo, logs, source maps, or TS source in the VSIX");

// Required contents still present.
const requiredEntries = [
  "extension/dist/extension.js",
  "extension/dist/mossWorker.js",
  "extension/node_modules/@moss-dev/moss/package.json",
  "extension/node_modules/@moss-dev/moss-core/package.json",
];
for (const rel of requiredEntries) {
  if (!listing.includes(rel)) fail(`VSIX missing required entry: ${rel}`);
}

// ---------------------------------------------------------------------------
// 3. Extract and assert bundled versions + hidden-hook absence.
// ---------------------------------------------------------------------------
const extractDir = mkdtempSync(path.join(os.tmpdir(), "moss-vsix-verify-"));
try {
  execSync(`unzip -q "${vsix}" -d "${extractDir}"`, { stdio: "inherit" });
  const modBase = path.join(extractDir, "extension", "node_modules");

  const bundledWrapper = JSON.parse(
    readFileSync(path.join(modBase, "@moss-dev", "moss", "package.json"), "utf8"),
  ).version;
  if (bundledWrapper !== FIXED_WRAPPER) {
    fail(`VSIX bundles @moss-dev/moss ${bundledWrapper}, expected exactly ${FIXED_WRAPPER}`);
  }
  const bundledCore = JSON.parse(
    readFileSync(path.join(modBase, "@moss-dev", "moss-core", "package.json"), "utf8"),
  ).version;
  if (bundledCore !== FIXED_CORE) {
    fail(`VSIX bundles @moss-dev/moss-core ${bundledCore}, expected exactly ${FIXED_CORE}`);
  }
  for (const pkg of PLATFORM_PACKAGES) {
    const pkgJson = path.join(modBase, ...pkg.split("/"), "package.json");
    if (!existsSync(pkgJson)) fail(`VSIX missing bundled platform package: ${pkg}`);
    const v = JSON.parse(readFileSync(pkgJson, "utf8")).version;
    if (v !== FIXED_CORE) fail(`VSIX platform package ${pkg} is ${v}, expected ${FIXED_CORE}`);
  }
  console.log(`✓ VSIX bundles fixed set: moss ${bundledWrapper} -> core ${bundledCore} (5 platforms)`);

  // Hidden test-hook / debug export scan. The shipped SDK JS and worker bundle
  // must not expose panic/test/debug hooks, and EVERY packaged platform .node
  // (not just the runner-native one) must carry no such symbols — a hook baked
  // into any of the five bundled binaries ships to that platform's users.
  const HOOK_RE = /__test_panic_hook|__debugWaiter|__debug[A-Z]|__test[A-Z]/;
  const scanJsFiles = [
    path.join(modBase, "@moss-dev", "moss", "dist", "index.esm.js"),
    path.join(modBase, "@moss-dev", "moss-core", "index.js"),
    path.join(extractDir, "extension", "dist", "mossWorker.js"),
    path.join(extractDir, "extension", "dist", "extension.js"),
  ];
  for (const f of scanJsFiles) {
    // A missing expected target must fail, not silently skip — otherwise a
    // layout change turns the hook assertion into a no-op.
    if (!existsSync(f)) fail(`expected JS scan target missing from VSIX: ${path.relative(extractDir, f)}`);
    if (HOOK_RE.test(readFileSync(f, "utf8"))) {
      fail(`hidden test-hook/debug export found in ${path.relative(extractDir, f)}`);
    }
  }
  const scannedNodes = [];
  for (const pkg of PLATFORM_PACKAGES) {
    const dir = path.join(modBase, ...pkg.split("/"));
    const nodeFile = existsSync(dir) ? readdirSync(dir).find((f) => f.endsWith(".node")) : undefined;
    if (!nodeFile) fail(`VSIX platform package ${pkg} is missing its .node binary`);
    const buf = readFileSync(path.join(dir, nodeFile));
    if (HOOK_RE.test(buf.toString("latin1"))) {
      fail(`hidden test-hook/debug symbol found in bundled native addon ${pkg}/${nodeFile}`);
    }
    scannedNodes.push(nodeFile);
  }
  console.log(`✓ no hidden test-hook/debug symbols (JS + all ${scannedNodes.length} platform .node binaries)`);

  // -------------------------------------------------------------------------
  // 4. Execute the EXTRACTED worker against the VSIX's own bundled .node.
  // -------------------------------------------------------------------------
  await executePackagedWorker(extractDir);
  console.log(`✓ extracted worker survives a torn cache against its bundled .node`);
} finally {
  rmSync(extractDir, { recursive: true, force: true });
}

console.log(`Package verification passed (${path.basename(vsix)}).`);

// ---------------------------------------------------------------------------
// Helpers.
// ---------------------------------------------------------------------------
async function executePackagedWorker(extractDir) {
  const { startAuthStub } = await import("../test/support/authStub.mjs");
  const { buildBaselineCacheWith, makeCorruptCache, makeTempRoot, safeRm } = await import(
    "../test/support/fixtures.mjs"
  );
  const { WorkerHarness } = await import("../test/support/workerHarness.mjs");
  const { SESSION_NAME, STUB_PROJECT_ID, STUB_PROJECT_KEY, applyHermeticEnv } = await import(
    "../test/support/env.mjs"
  );

  // Disable parent-process telemetry and isolate its model cache BEFORE the
  // bundled SDK is imported/constructed for baseline generation.
  applyHermeticEnv();

  const workerPath = path.join(extractDir, "extension", "dist", "mossWorker.js");
  const stub = await startAuthStub();
  const modelCache = makeTempRoot("vsix-modelcache");
  const fixturesRoot = makeTempRoot("vsix-baseline");
  // Generate the baseline cache using the VSIX's OWN bundled SDK, so the fixture
  // and the worker exercise the identical packaged native addon.
  const bundledSdk = path.join(extractDir, "extension", "node_modules", "@moss-dev", "moss");
  const baselineDir = await buildBaselineCacheWith(fixturesRoot, bundledSdk);

  const worker = new WorkerHarness(
    { MOSS_AUTH_URL: stub.authUrl, MOSS_INDEX_URL: stub.indexUrl, MOSS_MODEL_CACHE_DIR: modelCache },
    workerPath,
  );
  try {
    const init = await worker.call("initialize", {
      projectId: STUB_PROJECT_ID,
      projectKey: STUB_PROJECT_KEY,
      name: SESSION_NAME,
      modelId: "custom",
    });
    if (init.docCount !== 0) fail(`packaged worker init docCount=${init.docCount}, expected 0`);

    const tornRoot = makeTempRoot("vsix-torn");
    makeCorruptCache(baselineDir, tornRoot, "torn_vector_count");
    const res = await worker.send("loadFromDisk", { cachePath: tornRoot });
    if (res.ok !== false) fail("packaged worker did not reject a torn cache (possible abort)");
    if (worker.exit !== null) fail(`packaged worker exited after torn cache: ${JSON.stringify(worker.exit)}`);
    if (!worker.connected) fail("packaged worker not connected after torn cache");

    const docs = await worker.call("getDocs", { options: undefined });
    if (docs.docCount !== 0) fail("packaged worker installed partial state after failed load");
  } finally {
    await worker.dispose();
    await stub.close();
    // Worker is gone; releasing any mmap so best-effort cleanup is safe.
    safeRm(fixturesRoot);
    safeRm(modelCache);
  }
}

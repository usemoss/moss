// Layer 1 — Worker-survival E2E (MOS-166).
//
// Boots the REAL built worker (dist/mossWorker.js) exactly as the extension host
// does, initializes a session through a loopback auth stub (no real credentials
// or off-box network), then feeds a battery of deterministic torn/corrupt
// on-disk caches to `loadFromDisk`. For each one it asserts:
//   * the worker returns a catchable IPC error ({ ok: false }), not an abort;
//   * the worker process stays alive and IPC-connected;
//   * no partial state is installed (docCount unchanged); and
//   * the worker still answers a subsequent safe request.
//
// This runs against the real installed addon for the runner's platform. The CI
// matrix (macOS / Linux / Windows) exercises all three shipped native targets.
// The native `loadFromDisk` deserialize path is model-independent, so the
// hermetic `custom` model faithfully drives the same boundary the shipped
// `moss-minilm` sessions hit — see support/env.mjs.

import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import * as fs from "node:fs";
import { startAuthStub } from "./support/authStub.mjs";
import { buildBaselineCache, makeCorruptCache, makeTempRoot, CORRUPTIONS, SEED_DOCS } from "./support/fixtures.mjs";
import { WorkerHarness } from "./support/workerHarness.mjs";
import { SESSION_NAME, STUB_PROJECT_ID, STUB_PROJECT_KEY } from "./support/env.mjs";

let stub;
let worker;
let modelCacheDir;
let baselineDir;
let fixturesRoot;

before(async () => {
  stub = await startAuthStub();
  fixturesRoot = makeTempRoot("survival-baseline");
  baselineDir = await buildBaselineCache(fixturesRoot);

  modelCacheDir = makeTempRoot("survival-modelcache");
  worker = new WorkerHarness({
    MOSS_AUTH_URL: stub.authUrl,
    MOSS_INDEX_URL: stub.indexUrl,
    MOSS_MODEL_CACHE_DIR: modelCacheDir,
  });

  // Initialize exactly as the host does (see client.ts initialize()), but with a
  // hermetic, model-free `custom` session.
  const init = await worker.call("initialize", {
    projectId: STUB_PROJECT_ID,
    projectKey: STUB_PROJECT_KEY,
    name: SESSION_NAME,
    modelId: "custom",
  });
  assert.equal(init.docCount, 0, "fresh session starts empty");
  assert.ok(worker.connected, "worker connected after initialize");
});

after(async () => {
  await worker?.dispose();
  await stub?.close();
});

for (const corruptionName of Object.keys(CORRUPTIONS)) {
  test(`corrupt cache "${corruptionName}" -> catchable IPC error, worker survives`, async () => {
    const root = makeTempRoot(`survival-${corruptionName}`);
    makeCorruptCache(baselineDir, root, corruptionName);

    const res = await worker.send("loadFromDisk", { cachePath: root });

    assert.equal(res.ok, false, `loadFromDisk on ${corruptionName} must reject, not abort`);
    assert.equal(typeof res.error, "string");
    assert.ok(res.error.length > 0, "error message present");

    // Process-survival: still connected, no exit recorded.
    assert.equal(worker.exit, null, "worker must not have exited");
    assert.ok(worker.connected, "worker must remain IPC-connected");

    // No partial state installed by the failed load.
    const docs = await worker.call("getDocs", { options: undefined });
    assert.equal(docs.docCount, 0, "no partial documents installed after failed load");

    fs.rmSync(root, { recursive: true, force: true });
  });
}

test("worker answers a subsequent safe request after the fault battery", async () => {
  // A safe mutation succeeds (custom embeddings) — proves full liveness.
  const added = await worker.call("addDocs", { docs: SEED_DOCS });
  assert.equal(added.docCount, SEED_DOCS.length, "safe addDocs succeeds after faults");

  // A clean round-trip load of a valid baseline cache still works.
  const cleanRoot = makeTempRoot("survival-clean");
  fs.rmSync(cleanRoot, { recursive: true, force: true });
  fs.cpSync(baselineDir, `${cleanRoot}/${SESSION_NAME}`, { recursive: true });
  const loaded = await worker.call("loadFromDisk", { cachePath: cleanRoot });
  assert.equal(loaded.loaded, SEED_DOCS.length, "valid cache loads cleanly");
  assert.ok(worker.connected, "worker still connected at end");
  fs.rmSync(cleanRoot, { recursive: true, force: true });
});

test("no embedding model was downloaded (hermetic, offline)", () => {
  // The custom model loads nothing; the isolated model cache must be empty,
  // proving the gate did not reach the public model host.
  const entries = fs.existsSync(modelCacheDir) ? fs.readdirSync(modelCacheDir) : [];
  assert.deepEqual(entries, [], `model cache must stay empty, found: ${entries.join(", ")}`);
});

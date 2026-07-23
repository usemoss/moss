// Layer 3 — Supervisor negative control (MOS-166).
//
// Drives the REAL extension-host supervisor (src/moss/client.ts
// `MossSessionManager`, bundled with a vscode stub — no production change) and
// deliberately ABORTS its worker with a signal while a call is in flight. This
// is the counterpart to the worker-survival layer: it proves the host correctly
// handles the *uncatchable* failure mode (signal/abort), as opposed to the
// catchable-throw path.
//
// It asserts the supervisor:
//   * records the worker exit code/signal,
//   * rejects all pending calls (surfacing a crash error),
//   * clears session state, and
//   * starts a fresh replacement worker.
//
// Hermetic: the auth stub is held in "hang" mode so the worker blocks at the
// native credential-validation step (before any embedding model is touched),
// giving a deterministic in-flight call to abort and a model-free restart proof.

import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { startAuthStub } from "./support/authStub.mjs";
import { loadSupervisorModule } from "./support/loadSupervisor.mjs";
import { makeTempRoot } from "./support/fixtures.mjs";
import { STUB_PROJECT_ID, STUB_PROJECT_KEY } from "./support/env.mjs";

const APP_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function waitFor(predicate, { timeout = 10000, interval = 20 } = {}) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const tick = () => {
      let ok = false;
      try {
        ok = predicate();
      } catch {
        ok = false;
      }
      if (ok) return resolve();
      if (Date.now() - start > timeout) return reject(new Error("waitFor timed out"));
      setTimeout(tick, interval);
    };
    tick();
  });
}

let stub;
let MossSessionManager;
let modelCacheDir;

before(async () => {
  ({ MossSessionManager } = await loadSupervisorModule());
  stub = await startAuthStub({ hang: true });
  modelCacheDir = makeTempRoot("supervisor-modelcache");
  // ensureWorker() forks with {...process.env}; route the worker to the loopback
  // stub and an isolated model cache.
  process.env.MOSS_AUTH_URL = stub.authUrl;
  process.env.MOSS_INDEX_URL = stub.indexUrl;
  process.env.MOSS_MODEL_CACHE_DIR = modelCacheDir;
  process.env.MOSS_DISABLE_TELEMETRY = "1";
});

after(async () => {
  await stub?.close();
});

test("aborting the worker mid-call: records signal, rejects pending, clears state, restarts", async () => {
  const logs = [];
  const manager = new MossSessionManager(APP_ROOT, (m) => logs.push(m));
  const creds = { projectId: STUB_PROJECT_ID, projectKey: STUB_PROJECT_KEY };

  // 1) Start an initialize() that blocks at native auth (stub is hanging).
  const requestsBefore = stub.requests;
  const initPromise = manager.initialize(creds);
  initPromise.catch(() => {}); // handled via assert.rejects below

  // The worker is forked synchronously inside ensureWorker().
  const worker1 = manager.worker;
  assert.ok(worker1 && typeof worker1.pid === "number", "supervisor forked a worker");
  const pid1 = worker1.pid;

  // Wait until the worker actually reached the native credential validation,
  // i.e. a call is genuinely in flight.
  await waitFor(() => stub.requests > requestsBefore);

  // 2) Deliberately abort the worker with a signal (models a native abort).
  worker1.kill("SIGKILL");

  // 3) The pending initialize() call must be rejected as a crash, not hang.
  await assert.rejects(initPromise, /crash/i, "pending call rejected as a crash");

  // ...and the host must have recorded the exit code/signal. This is the
  // signal/abort path — the worker process actually EXITED, unlike the
  // catchable-throw path (worker-survival.test.mjs) where it stays alive.
  const exitLog = logs.find((l) => l.includes("Moss worker exited"));
  assert.ok(exitLog, "supervisor logged the worker exit");
  // Node reports a kill("SIGKILL") as signal=SIGKILL / code=null on Windows too.
  assert.match(exitLog, /signal=SIGKILL/, "recorded the abort signal (distinguishes signal/abort)");
  assert.match(exitLog, /code=null/, "no ordinary exit code on a signal death");

  // 4) State cleared.
  assert.equal(manager.isReady, false, "not ready after crash");
  assert.throws(() => manager.getSession(), /not initialized/, "session cleared after crash");
  assert.equal(manager.worker, undefined, "worker handle cleared after crash");

  // 5) A fresh initialize() starts a REPLACEMENT worker (new process, connected,
  //    reaching the native layer). Kept in hang mode -> model-free restart proof.
  const requestsBeforeRestart = stub.requests;
  const restartPromise = manager.initialize(creds);
  restartPromise.catch(() => {}); // torn down in cleanup

  await waitFor(() => manager.worker && manager.worker.pid !== pid1 && manager.worker.connected);
  const pid2 = manager.worker.pid;
  assert.notEqual(pid2, pid1, "replacement worker is a new process");
  await waitFor(() => stub.requests > requestsBeforeRestart);
  assert.ok(manager.worker.connected, "replacement worker is IPC-connected");

  // Cleanup: dispose rejects the still-pending restart call.
  manager.dispose();
  await restartPromise.catch(() => {});

  // Model-free: the isolated cache stayed empty (worker never passed auth).
  const entries = fs.existsSync(modelCacheDir) ? fs.readdirSync(modelCacheDir) : [];
  assert.deepEqual(entries, [], `model cache must stay empty, found: ${entries.join(", ")}`);
});

// Forks the built worker (dist/mossWorker.js) exactly as the extension host does
// in src/moss/client.ts (IPC stdio layout, ELECTRON_RUN_AS_NODE, the same
// {id, method, args} -> {id, ok, result|error} request/response protocol), so
// the regression test drives the real shipped worker over the real IPC boundary.

import { fork } from "node:child_process";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { workerEnv } from "./env.mjs";

const APP_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
export const WORKER_PATH = path.join(APP_ROOT, "dist", "mossWorker.js");

export class WorkerHarness {
  constructor(envExtra = {}, workerPath = WORKER_PATH) {
    this._nextId = 1;
    this._pending = new Map();
    this.exit = null; // { code, signal } once the worker exits
    this._worker = fork(workerPath, [], {
      stdio: ["ignore", "pipe", "pipe", "ipc"],
      execPath: process.execPath,
      env: workerEnv(envExtra),
    });
    this.stderr = "";
    this._worker.stderr?.on("data", (c) => (this.stderr += c.toString()));

    this._worker.on("message", (msg) => {
      const pending = this._pending.get(msg.id);
      if (!pending) return;
      this._pending.delete(msg.id);
      if (msg.ok) pending.resolve(msg);
      else pending.resolve(msg); // {ok:false} is a value, not a throw, for assertions
    });
    this._worker.on("exit", (code, signal) => {
      this.exit = { code, signal };
      for (const { reject } of this._pending.values()) {
        reject(new Error(`worker exited (code=${code}, signal=${signal})`));
      }
      this._pending.clear();
    });
  }

  get connected() {
    return !!this._worker.connected && this.exit === null;
  }

  get pid() {
    return this._worker.pid;
  }

  /** Send a request; resolves with the raw response envelope ({ok:true|false}). */
  send(method, args) {
    const id = this._nextId++;
    return new Promise((resolve, reject) => {
      this._pending.set(id, { resolve, reject });
      this._worker.send({ id, method, args }, (err) => {
        if (err) {
          this._pending.delete(id);
          reject(err);
        }
      });
    });
  }

  /** Send a request and require it to succeed, returning `result`. */
  async call(method, args) {
    const res = await this.send(method, args);
    if (!res.ok) throw new Error(`worker call ${method} failed: ${res.error}`);
    return res.result;
  }

  kill(signal = "SIGKILL") {
    this._worker.kill(signal);
  }

  /** Wait for the worker to exit; resolves with { code, signal }. */
  waitForExit() {
    if (this.exit) return Promise.resolve(this.exit);
    return new Promise((resolve) => this._worker.once("exit", (code, signal) => resolve({ code, signal })));
  }

  async dispose() {
    if (this.exit === null) {
      this._worker.kill();
      await this.waitForExit().catch(() => {});
    }
  }
}

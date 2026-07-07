import { randomUUID } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";

const DEVICE_ID_FILE = ".moss-device-id";
const DEFAULT_DIR_NAME = ".moss";
const TRUTHY = new Set(["1", "true", "yes", "on"]);

/** True when usage telemetry is disabled via `MOSS_DISABLE_TELEMETRY`. */
export function telemetryDisabled(env: NodeJS.ProcessEnv = process.env): boolean {
  const v = env.MOSS_DISABLE_TELEMETRY;
  return v != null && TRUTHY.has(v.trim().toLowerCase());
}

/**
 * Resolve the stable per-device id persisted at `<cachePath>/.moss-device-id`.
 * Reads an existing UUID, or generates and writes one. Returns `undefined`
 * when telemetry is disabled. On a filesystem error, returns a fresh ephemeral
 * UUID (not persisted) so telemetry can still attribute within this run —
 * device-id persistence must never break `loadIndex`.
 */
export function resolveDeviceId(
  cachePath: string,
  env: NodeJS.ProcessEnv = process.env,
): string | undefined {
  if (telemetryDisabled(env)) return undefined;
  try {
    const dir = resolve(cachePath);
    const file = join(dir, DEVICE_ID_FILE);
    if (existsSync(file)) {
      const existing = readFileSync(file, "utf8").trim();
      if (existing) return existing;
    }
    mkdirSync(dir, { recursive: true });
    const id = randomUUID();
    writeFileSync(file, id, "utf8");
    return id;
  } catch {
    return randomUUID();
  }
}

/**
 * Per-user fallback directory for the device-id file, used when no `cachePath`
 * is available — most notably the cloud-fallback query path, which has no
 * cache directory of its own. Resolves to `<home>/.moss`, where `home` comes
 * from `$HOME` / `%USERPROFILE%` (falling back to `os.homedir()`). A single
 * per-user location keeps a device's id stable across processes that never
 * pass a `cachePath`, so it counts once toward Monthly Active Devices.
 */
export function defaultDeviceIdDir(env: NodeJS.ProcessEnv = process.env): string {
  // `||` (not `??`) + trim so a blank `$HOME` / `%USERPROFILE%` falls through
  // to `os.homedir()` rather than producing a relative `.moss` (which would
  // land in the current working directory).
  const home = env.HOME?.trim() || env.USERPROFILE?.trim() || homedir();
  return join(home, DEFAULT_DIR_NAME);
}

export interface DeviceIdTarget {
  // Optional: newer moss-core builds expose the napi `setDeviceId` setter;
  // older `.node` builds do not (handled as terminal success in `applyDeviceId`).
  setDeviceId?(deviceId: string): void;
}

export interface DeviceIdState {
  id?: string;
  applied: boolean;
}

/**
 * Resolve the client's stable device id once and memoize it on `state`, so
 * every telemetry surface a client touches reports the same id — one device,
 * one id. Persists under `cachePath` when given, otherwise under the per-user
 * fallback dir. Returns `undefined` (without memoizing) when telemetry is
 * disabled.
 */
export function resolveClientDeviceId(
  state: DeviceIdState,
  cachePath: string | undefined,
  env: NodeJS.ProcessEnv = process.env,
): string | undefined {
  // Check disabled first, before the memoized fast-path, so toggling
  // MOSS_DISABLE_TELEMETRY at runtime stops attribution immediately.
  if (telemetryDisabled(env)) return undefined;
  if (state.id) return state.id;
  // Treat a blank cachePath as absent — `resolve("")` would point at the CWD.
  const dir = cachePath?.trim() ? cachePath : defaultDeviceIdDir(env);
  const id = resolveDeviceId(dir, env);
  if (id) state.id = id;
  return id;
}

/**
 * Push `id` to a telemetry `target`. Best-effort: never throws. Returns whether
 * the id is now settled — `true` on success, or when the target's moss-core
 * build predates `setDeviceId` (terminal: a newer binding won't appear
 * mid-process, so there's nothing to retry). Returns `false` only when the
 * call threw, so the caller may retry later.
 */
export function applyDeviceId(target: DeviceIdTarget, id: string): boolean {
  if (typeof target.setDeviceId !== "function") return true;
  try {
    target.setDeviceId(id);
    return true;
  } catch {
    return false;
  }
}

/**
 * Resolve the device id (once, shared via `state`) and push it to `target`.
 * No-op once applied or when telemetry is disabled. Used for the long-lived
 * IndexManager. On a transient failure `state.applied` stays false so the next
 * call retries rather than permanently suppressing the id.
 */
export function applyDeviceIdOnce(
  target: DeviceIdTarget,
  state: DeviceIdState,
  cachePath: string | undefined,
  env: NodeJS.ProcessEnv = process.env,
): void {
  if (state.applied) return;
  const id = resolveClientDeviceId(state, cachePath, env);
  if (!id) return;
  state.applied = applyDeviceId(target, id);
}

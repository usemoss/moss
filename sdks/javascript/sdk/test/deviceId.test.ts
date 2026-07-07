import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, isAbsolute } from "node:path";
import {
  telemetryDisabled,
  resolveDeviceId,
  resolveClientDeviceId,
  defaultDeviceIdDir,
  applyDeviceId,
  applyDeviceIdOnce,
  type DeviceIdState,
} from "../src/utils/deviceId";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

describe("deviceId", () => {
  let dir: string;
  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), "moss-devid-"));
  });
  afterEach(() => {
    rmSync(dir, { recursive: true, force: true });
  });

  // --- resolveDeviceId ---

  it("creates and persists a UUID on first resolve", () => {
    const id = resolveDeviceId(dir, {});
    expect(id).toMatch(UUID_RE);
    const file = join(dir, ".moss-device-id");
    expect(existsSync(file)).toBe(true);
    expect(readFileSync(file, "utf8").trim()).toBe(id);
  });

  it("returns the same id on subsequent resolves", () => {
    const first = resolveDeviceId(dir, {});
    const second = resolveDeviceId(dir, {});
    expect(second).toBe(first);
  });

  it("honors a pre-seeded id file", () => {
    writeFileSync(join(dir, ".moss-device-id"), "preseeded-id-1", "utf8");
    expect(resolveDeviceId(dir, {})).toBe("preseeded-id-1");
  });

  it("returns undefined when telemetry is disabled", () => {
    expect(resolveDeviceId(dir, { MOSS_DISABLE_TELEMETRY: "true" })).toBeUndefined();
    expect(existsSync(join(dir, ".moss-device-id"))).toBe(false);
  });

  it("telemetryDisabled parses common truthy values", () => {
    expect(telemetryDisabled({ MOSS_DISABLE_TELEMETRY: "1" })).toBe(true);
    expect(telemetryDisabled({ MOSS_DISABLE_TELEMETRY: "TRUE" })).toBe(true);
    expect(telemetryDisabled({})).toBe(false);
    expect(telemetryDisabled({ MOSS_DISABLE_TELEMETRY: "0" })).toBe(false);
  });

  // --- defaultDeviceIdDir ---

  it("defaultDeviceIdDir resolves to <home>/.moss from $HOME", () => {
    expect(defaultDeviceIdDir({ HOME: "/home/u" })).toBe(join("/home/u", ".moss"));
  });

  it("defaultDeviceIdDir falls back to %USERPROFILE% (Windows)", () => {
    expect(defaultDeviceIdDir({ USERPROFILE: "C:\\Users\\u" })).toBe(
      join("C:\\Users\\u", ".moss"),
    );
  });

  it("defaultDeviceIdDir ignores a blank $HOME (would otherwise resolve to CWD)", () => {
    // A blank HOME must fall through, not produce a relative ".moss".
    expect(defaultDeviceIdDir({ HOME: "  ", USERPROFILE: "C:\\Users\\u" })).toBe(
      join("C:\\Users\\u", ".moss"),
    );
    expect(isAbsolute(defaultDeviceIdDir({ HOME: "" }))).toBe(true);
  });

  // --- resolveClientDeviceId ---

  it("resolveClientDeviceId persists under cachePath when provided", () => {
    const state: DeviceIdState = { applied: false };
    const id = resolveClientDeviceId(state, dir, {});
    expect(id).toMatch(UUID_RE);
    expect(readFileSync(join(dir, ".moss-device-id"), "utf8").trim()).toBe(id);
    expect(state.id).toBe(id);
  });

  it("resolveClientDeviceId falls back to <home>/.moss when no cachePath", () => {
    const state: DeviceIdState = { applied: false };
    const id = resolveClientDeviceId(state, undefined, { HOME: dir });
    expect(id).toMatch(UUID_RE);
    expect(readFileSync(join(dir, ".moss", ".moss-device-id"), "utf8").trim()).toBe(id);
  });

  it("resolveClientDeviceId memoizes the first id across calls and locations", () => {
    const state: DeviceIdState = { applied: false };
    const first = resolveClientDeviceId(state, dir, {});
    // A later call with no cachePath must reuse the memoized id, not mint a
    // second one from the fallback dir — one device, one id.
    const second = resolveClientDeviceId(state, undefined, { HOME: join(dir, "other") });
    expect(second).toBe(first);
    expect(existsSync(join(dir, "other", ".moss", ".moss-device-id"))).toBe(false);
  });

  it("resolveClientDeviceId returns undefined and does not memoize when telemetry disabled", () => {
    const state: DeviceIdState = { applied: false };
    expect(resolveClientDeviceId(state, dir, { MOSS_DISABLE_TELEMETRY: "1" })).toBeUndefined();
    expect(state.id).toBeUndefined();
  });

  it("resolveClientDeviceId honors a runtime telemetry-disable even after an id was memoized", () => {
    const state: DeviceIdState = { id: "preset-id", applied: true };
    expect(resolveClientDeviceId(state, dir, { MOSS_DISABLE_TELEMETRY: "1" })).toBeUndefined();
  });

  it("resolveClientDeviceId treats a blank cachePath as absent and uses the fallback dir", () => {
    const state: DeviceIdState = { applied: false };
    const id = resolveClientDeviceId(state, "   ", { HOME: dir });
    expect(id).toMatch(UUID_RE);
    // Persisted to the fallback dir, not the CWD (`resolve("   ")`).
    expect(readFileSync(join(dir, ".moss", ".moss-device-id"), "utf8").trim()).toBe(id);
  });

  // --- applyDeviceId ---

  it("applyDeviceId pushes the id to the target and reports success", () => {
    const calls: string[] = [];
    const ok = applyDeviceId({ setDeviceId: (d: string) => calls.push(d) }, "abc");
    expect(ok).toBe(true);
    expect(calls).toEqual(["abc"]);
  });

  it("applyDeviceId treats a missing setDeviceId (older binding) as terminal success", () => {
    const target = {} as unknown as { setDeviceId: (d: string) => void };
    expect(applyDeviceId(target, "abc")).toBe(true);
  });

  it("applyDeviceId reports failure when setDeviceId throws (so the caller can retry)", () => {
    const target = {
      setDeviceId: () => {
        throw new Error("transient binding error");
      },
    };
    expect(applyDeviceId(target, "abc")).toBe(false);
  });

  // --- applyDeviceIdOnce ---

  it("applyDeviceIdOnce sets the id exactly once and memoizes", () => {
    const calls: string[] = [];
    const target = { setDeviceId: (d: string) => calls.push(d) };
    const state: DeviceIdState = { applied: false };

    applyDeviceIdOnce(target, state, dir, {});
    applyDeviceIdOnce(target, state, dir, {});
    expect(calls.length).toBe(1);
    expect(calls[0]).toMatch(UUID_RE);
    expect(state.id).toBe(calls[0]);
  });

  it("applyDeviceIdOnce falls back to the default device-id dir when no cachePath", () => {
    const calls: string[] = [];
    const target = { setDeviceId: (d: string) => calls.push(d) };
    const state: DeviceIdState = { applied: false };
    applyDeviceIdOnce(target, state, undefined, { HOME: dir });
    expect(calls.length).toBe(1);
    expect(calls[0]).toMatch(UUID_RE);
    expect(state.applied).toBe(true);
    expect(existsSync(join(dir, ".moss", ".moss-device-id"))).toBe(true);
  });

  it("applyDeviceIdOnce does nothing when telemetry disabled", () => {
    const calls: string[] = [];
    const target = { setDeviceId: (d: string) => calls.push(d) };
    const state: DeviceIdState = { applied: false };
    applyDeviceIdOnce(target, state, dir, { MOSS_DISABLE_TELEMETRY: "yes" });
    expect(calls.length).toBe(0);
  });

  it("applyDeviceIdOnce marks applied without throwing when setDeviceId is absent (older binding)", () => {
    const target = {} as unknown as { setDeviceId: (d: string) => void };
    const state: DeviceIdState = { applied: false };
    expect(() => applyDeviceIdOnce(target, state, dir, {})).not.toThrow();
    expect(state.applied).toBe(true);
  });

  it("applyDeviceIdOnce leaves applied=false (retries) when setDeviceId throws", () => {
    let calls = 0;
    const target = {
      setDeviceId: () => {
        calls++;
        throw new Error("transient binding error");
      },
    };
    const state: DeviceIdState = { applied: false };
    expect(() => applyDeviceIdOnce(target, state, dir, {})).not.toThrow();
    expect(state.applied).toBe(false);
    applyDeviceIdOnce(target, state, dir, {}); // retried on next call
    expect(calls).toBe(2);
  });
});

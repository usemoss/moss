import { describe, expect, it, vi } from "vitest";
import {
  clearLocalIndexLoadState,
  ensureLocalIndexLoaded,
  notifySearchIndexStale,
  registerSearchIndexStaleHandler,
  type LocalIndexLoadState,
} from "../src/mossQueryState.js";

describe("ensureLocalIndexLoaded", () => {
  it("loads once and records loaded index", async () => {
    const loadIndex = vi.fn().mockResolvedValue(undefined);
    const client = { loadIndex } as { loadIndex: (n: string) => Promise<string> };
    const state: LocalIndexLoadState = {};
    await ensureLocalIndexLoaded(client as never, "idx-a", state);
    expect(loadIndex).toHaveBeenCalledTimes(1);
    expect(loadIndex).toHaveBeenCalledWith("idx-a");
    expect(state.loadedIndexName).toBe("idx-a");
    await ensureLocalIndexLoaded(client as never, "idx-a", state);
    expect(loadIndex).toHaveBeenCalledTimes(1);
  });

  it("sets localLoadFailedIndex and skips further load attempts for that index", async () => {
    const loadIndex = vi
      .fn()
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValue(undefined);
    const client = { loadIndex } as { loadIndex: (n: string) => Promise<string> };
    const state: LocalIndexLoadState = {};
    await expect(
      ensureLocalIndexLoaded(client as never, "idx-b", state)
    ).rejects.toThrow("network");
    expect(state.localLoadFailedIndex).toBe("idx-b");
    expect(state.loadedIndexName).toBeUndefined();
    await ensureLocalIndexLoaded(client as never, "idx-b", state);
    expect(loadIndex).toHaveBeenCalledTimes(1);
  });

  it("still loads another index after a different index failed", async () => {
    const loadIndex = vi
      .fn()
      .mockRejectedValueOnce(new Error("fail-a"))
      .mockResolvedValue(undefined);
    const client = { loadIndex } as { loadIndex: (n: string) => Promise<string> };
    const state: LocalIndexLoadState = {};
    await expect(
      ensureLocalIndexLoaded(client as never, "idx-a", state)
    ).rejects.toThrow("fail-a");
    await ensureLocalIndexLoaded(client as never, "idx-b", state);
    expect(loadIndex).toHaveBeenCalledTimes(2);
    expect(state.loadedIndexName).toBe("idx-b");
  });

  it("retries same index after clearLocalIndexLoadState", async () => {
    const loadIndex = vi
      .fn()
      .mockRejectedValueOnce(new Error("x"))
      .mockResolvedValue(undefined);
    const client = { loadIndex } as { loadIndex: (n: string) => Promise<string> };
    const state: LocalIndexLoadState = {};
    await expect(
      ensureLocalIndexLoaded(client as never, "idx", state)
    ).rejects.toThrow("x");
    clearLocalIndexLoadState(state);
    await ensureLocalIndexLoaded(client as never, "idx", state);
    expect(loadIndex).toHaveBeenCalledTimes(2);
    expect(state.loadedIndexName).toBe("idx");
  });
});

describe("clearLocalIndexLoadState", () => {
  it("clears loaded and failure fields", () => {
    const state: LocalIndexLoadState = {
      loadedIndexName: "x",
      localLoadFailedIndex: "x",
    };
    clearLocalIndexLoadState(state);
    expect(state.loadedIndexName).toBeUndefined();
    expect(state.localLoadFailedIndex).toBeUndefined();
  });
});

describe("registerSearchIndexStaleHandler", () => {
  it("notifies all registered handlers and supports dispose", () => {
    const a = vi.fn();
    const b = vi.fn();
    const da = registerSearchIndexStaleHandler(a);
    const db = registerSearchIndexStaleHandler(b);
    notifySearchIndexStale();
    expect(a).toHaveBeenCalledTimes(1);
    expect(b).toHaveBeenCalledTimes(1);
    da.dispose();
    notifySearchIndexStale();
    expect(a).toHaveBeenCalledTimes(1);
    expect(b).toHaveBeenCalledTimes(2);
    db.dispose();
  });
});

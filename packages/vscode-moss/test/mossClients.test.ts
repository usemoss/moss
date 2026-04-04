import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@inferedge-rest/moss", () => ({
  MossRestClient: vi.fn(),
}));

vi.mock("@inferedge/moss", () => ({
  MossClient: vi.fn(),
}));

import { MossClient } from "@inferedge/moss";
import { MossRestClient } from "@inferedge-rest/moss";
import { createRestClient, createSdkClient } from "../src/mossClients.js";

describe("mossClients factories", () => {
  beforeEach(() => {
    vi.mocked(MossRestClient).mockReset();
    vi.mocked(MossClient).mockReset();
    vi.mocked(MossRestClient).mockImplementation(
      () =>
        ({
          deleteIndex: vi.fn().mockRejectedValue(new Error("network down")),
        }) as unknown as InstanceType<typeof MossRestClient>
    );
    vi.mocked(MossClient).mockImplementation(
      () =>
        ({
          loadIndex: vi.fn().mockResolvedValue("idx"),
        }) as unknown as InstanceType<typeof MossClient>
    );
  });

  it("createRestClient passes project id and key to MossRestClient", () => {
    createRestClient("proj-1", "key-1");
    expect(MossRestClient).toHaveBeenCalledWith("proj-1", "key-1");
  });

  it("createSdkClient passes project id and key to MossClient", () => {
    createSdkClient("proj-2", "key-2");
    expect(MossClient).toHaveBeenCalledWith("proj-2", "key-2");
  });

  it("rest client method errors propagate (wrapper is thin)", async () => {
    const client = createRestClient("a", "b");
    await expect(client.deleteIndex("x")).rejects.toThrow("network down");
  });

  it("sdk client returns mocked success path", async () => {
    const client = createSdkClient("a", "b");
    await expect(client.loadIndex("i")).resolves.toBe("idx");
  });
});

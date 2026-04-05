import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@moss-dev/moss", () => ({
  MossClient: vi.fn(),
}));

import { MossClient } from "@moss-dev/moss";
import { createRestClient, createSdkClient } from "../src/mossClients.js";

describe("mossClients factories", () => {
  beforeEach(() => {
    vi.mocked(MossClient).mockReset();
    vi.mocked(MossClient).mockImplementation(
      () =>
        ({
          deleteIndex: vi.fn().mockRejectedValue(new Error("network down")),
          loadIndex: vi.fn().mockResolvedValue("idx"),
        }) as unknown as InstanceType<typeof MossClient>
    );
  });

  it("createRestClient passes project id and key to MossClient", () => {
    createRestClient("proj-1", "key-1");
    expect(MossClient).toHaveBeenCalledWith("proj-1", "key-1");
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

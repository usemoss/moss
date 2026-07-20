// Node-floor alignment (MOS-166, finding #3 / captain Option A).
//
// The packaged @moss-dev/moss 1.4.1 declares engines.node ">=20.4", so the
// extension must not run its worker on an older Node. These assertions exercise
// the REAL version-gate helpers exported from src/moss/client.ts (bundled with a
// vscode stub, no production change) that findNodeBinary uses to reject a
// too-old candidate binary.

import { test } from "node:test";
import assert from "node:assert/strict";
import { loadSupervisorModule } from "./support/loadSupervisor.mjs";

test("worker Node floor is 20.4 and enforced correctly", async () => {
  const { MIN_WORKER_NODE_VERSION, parseNodeVersion, nodeMeetsWorkerFloor } =
    await loadSupervisorModule();

  assert.equal(MIN_WORKER_NODE_VERSION, "20.4.0", "floor matches the SDK's engines.node >=20.4");

  assert.deepEqual(parseNodeVersion("v20.4.0"), { major: 20, minor: 4, patch: 0 });
  assert.deepEqual(parseNodeVersion("20.10.1"), { major: 20, minor: 10, patch: 1 });
  assert.equal(parseNodeVersion(undefined), undefined);
  assert.equal(parseNodeVersion("not-a-version"), undefined);

  // At or above the floor.
  for (const ok of ["20.4.0", "v20.4.0", "20.4.9", "20.10.0", "21.0.0", "22.11.0"]) {
    assert.equal(nodeMeetsWorkerFloor(ok), true, `${ok} should meet the floor`);
  }
  // Below the floor or unparseable.
  for (const bad of ["20.3.9", "20.0.0", "18.19.0", "16.20.2", undefined, "", "garbage"]) {
    assert.equal(nodeMeetsWorkerFloor(bad), false, `${bad} should not meet the floor`);
  }
});

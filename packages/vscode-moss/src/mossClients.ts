import { MossRestClient } from "@inferedge-rest/moss";
import { MossClient } from "@inferedge/moss";

/** Thin factory for tests and to keep Moss imports in one place. */
export function createRestClient(projectId: string, projectKey: string): MossRestClient {
  return new MossRestClient(projectId, projectKey);
}

export function createSdkClient(projectId: string, projectKey: string): MossClient {
  return new MossClient(projectId, projectKey);
}

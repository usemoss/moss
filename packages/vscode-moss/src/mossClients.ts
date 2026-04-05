import { MossClient } from "@moss-dev/moss";

/** Thin factory for tests and to keep Moss imports in one place. */
export function createRestClient(projectId: string, projectKey: string): MossClient {
  return new MossClient(projectId, projectKey);
}

export function createSdkClient(projectId: string, projectKey: string): MossClient {
  return new MossClient(projectId, projectKey);
}

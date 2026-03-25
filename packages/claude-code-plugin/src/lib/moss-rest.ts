const BASE_URL = "https://service.usemoss.dev";
const QUERY_URL = `${BASE_URL}/query`;
const MANAGE_URL = `${BASE_URL}/v1/manage`;

export interface MossQueryResult {
  docs: Array<{
    id: string;
    text: string;
    score: number;
    metadata?: Record<string, string>;
  }>;
  timeTakenInMs?: number;
}

export async function cloudQuery(opts: {
  projectId: string;
  projectKey: string;
  indexName: string;
  query: string;
  topK?: number;
}): Promise<MossQueryResult> {
  const res = await fetch(QUERY_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query: opts.query,
      indexName: opts.indexName,
      projectId: opts.projectId,
      projectKey: opts.projectKey,
      topK: opts.topK ?? 3,
    }),
    signal: AbortSignal.timeout(4000),
  });
  if (!res.ok) throw new Error(`Moss /query: HTTP ${res.status}`);
  return (await res.json()) as MossQueryResult;
}

interface MossDoc {
  id: string;
  text: string;
  metadata?: Record<string, string>;
}

async function manage(opts: {
  projectId: string;
  projectKey: string;
  action: string;
  data?: Record<string, unknown>;
}): Promise<unknown> {
  const res = await fetch(MANAGE_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Project-Key": opts.projectKey,
    },
    body: JSON.stringify({
      action: opts.action,
      projectId: opts.projectId,
      ...opts.data,
    }),
    signal: AbortSignal.timeout(60_000),
  });
  if (!res.ok) throw new Error(`Moss /v1/manage ${opts.action}: HTTP ${res.status}`);
  return res.json();
}

export async function cloudAddDocs(opts: {
  projectId: string;
  projectKey: string;
  indexName: string;
  docs: MossDoc[];
  upsert?: boolean;
}): Promise<unknown> {
  return manage({
    projectId: opts.projectId,
    projectKey: opts.projectKey,
    action: "addDocs",
    data: {
      indexName: opts.indexName,
      docs: opts.docs,
      options: { upsert: opts.upsert ?? true },
    },
  });
}

export async function cloudDeleteDocs(opts: {
  projectId: string;
  projectKey: string;
  indexName: string;
  docIds: string[];
}): Promise<unknown> {
  return manage({
    projectId: opts.projectId,
    projectKey: opts.projectKey,
    action: "deleteDocs",
    data: {
      indexName: opts.indexName,
      docIds: opts.docIds,
    },
  });
}

export async function cloudCreateIndex(opts: {
  projectId: string;
  projectKey: string;
  indexName: string;
  docs: MossDoc[];
  modelId?: string;
}): Promise<unknown> {
  return manage({
    projectId: opts.projectId,
    projectKey: opts.projectKey,
    action: "createIndex",
    data: {
      indexName: opts.indexName,
      docs: opts.docs,
      modelId: opts.modelId ?? "moss-minilm",
    },
  });
}

export async function cloudListIndexes(opts: {
  projectId: string;
  projectKey: string;
}): Promise<unknown> {
  return manage({
    projectId: opts.projectId,
    projectKey: opts.projectKey,
    action: "listIndexes",
  });
}

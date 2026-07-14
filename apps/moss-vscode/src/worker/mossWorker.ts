import type {
  DocumentInfo,
  GetDocumentsOptions,
  MossClient,
  MutationOptions,
  PushIndexResult,
  QueryOptions,
  SearchResult,
  SessionIndex,
} from "@moss-dev/moss";

type Request = {
  id: number;
  method:
    | "initialize"
    | "addDocs"
    | "deleteDocs"
    | "query"
    | "getDocs"
    | "loadIndex"
    | "pushIndex"
    | "saveToDisk"
    | "loadFromDisk";
  args: unknown;
};

let client: MossClient | undefined;
let session: SessionIndex | undefined;

function send(
  id: number,
  payload: { ok: true; result: unknown } | { ok: false; error: string },
): void {
  process.send?.({ id, ...payload });
}

async function getMoss(): Promise<typeof import("@moss-dev/moss")> {
  return import("@moss-dev/moss");
}

function requireSession(): SessionIndex {
  if (!session) {
    throw new Error("Moss worker session is not initialized");
  }
  return session;
}

async function handle(method: Request["method"], args: unknown): Promise<unknown> {
  if (method === "initialize") {
    const init = args as {
      projectId: string;
      projectKey: string;
      name: string;
      modelId: "moss-minilm" | "moss-mediumlm";
    };
    const { MossClient: MossClientCtor } = await getMoss();
    client = new MossClientCtor(init.projectId, init.projectKey);
    session = await client.session(init.name, init.modelId);
    return { docCount: session.docCount };
  }

  if (method === "addDocs") {
    const { docs, options } = args as {
      docs: DocumentInfo[];
      options?: MutationOptions;
    };
    const result = await requireSession().addDocs(docs, options);
    return { ...result, docCount: requireSession().docCount };
  }

  if (method === "deleteDocs") {
    const { docIds } = args as { docIds: string[] };
    const deleted = await requireSession().deleteDocs(docIds);
    return { deleted, docCount: requireSession().docCount };
  }

  if (method === "query") {
    const { query, options } = args as {
      query: string;
      options?: QueryOptions;
    };
    const result: SearchResult = await requireSession().query(query, options);
    return result;
  }

  if (method === "getDocs") {
    const { options } = args as { options?: GetDocumentsOptions };
    const docs = await requireSession().getDocs(options);
    return { docs, docCount: requireSession().docCount };
  }

  if (method === "loadIndex") {
    const { indexName } = args as { indexName: string };
    const loaded = await requireSession().loadIndex(indexName);
    return { loaded, docCount: requireSession().docCount };
  }

  if (method === "pushIndex") {
    const result: PushIndexResult = await requireSession().pushIndex();
    return { ...result, docCount: requireSession().docCount };
  }

  if (method === "saveToDisk") {
    const { cachePath } = args as { cachePath: string };
    await requireSession().saveToDisk(cachePath);
    return { docCount: requireSession().docCount };
  }

  if (method === "loadFromDisk") {
    const { cachePath } = args as { cachePath: string };
    const loaded = await requireSession().loadFromDisk(cachePath);
    return { loaded, docCount: requireSession().docCount };
  }

  throw new Error(`Unknown Moss worker method: ${method}`);
}

process.on("message", async (message: Request) => {
  try {
    const result = await handle(message.method, message.args);
    send(message.id, { ok: true, result });
  } catch (err) {
    const error = err instanceof Error ? err.stack ?? err.message : String(err);
    send(message.id, { ok: false, error });
  }
});

process.on("uncaughtException", (err) => {
  console.error(err.stack ?? err.message);
  process.exit(1);
});

process.on("unhandledRejection", (reason) => {
  console.error(reason);
  process.exit(1);
});

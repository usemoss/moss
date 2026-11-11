# Moss client library for JavaScript


`@moss-js/moss` enables **private, on-device semantic search** in your web, mobile, and edge applications - without cloud dependencies.

Built for developers who want **instant, memory-efficient, privacy-first AI features** inside their apps.

## ✨ Features

- ⚡ **On-Device Vector Search** - Sub-millisecond retrieval with zero network latency
- 🔍 **Semantic Search & Hybrid Search** - Beyond keyword matching
- 📦 **Multi-Index Support** - Manage multiple isolated search spaces
- 🛠️ **Tiny SDK** - Optimized for edge deployments
- 🛡️ **Privacy-First by Design** - No server-side cloud calls required to perform searches

## 📦 Installation

```bash
npm install @moss-js/moss
```

## 🚀 Quick Start

```typescript
import { MossClient, DocumentInfo } from "@moss-js/moss";

async function main() {
  // Initialize search client with project credentials
  const mossClient = new MossClient(
    "your-project-id",
    "your-project-key"
  );

  // Prepare documents to index
  const documents: DocumentInfo[] = [
    {
      id: "doc1",
      text: "How do I track my order? You can track your order by logging into your account.",
    },
    {
      id: "doc2", 
      text: "What is your return policy? We offer a 30-day return policy for most items.",
    },
    {
      id: "doc3",
      text: "How can I change my shipping address? Contact our customer service team.",
    },
    // Add more documents here
    // .
    // .
    // .
  ];

  try {
    // Create an index with documents and model
    const indexName = "faqs";
    const created = await mossClient.createIndex(
      indexName,
      documents
    ); // Defaults to the service's `moss-minilm` model when omitted
    console.log("Index created:", created);

    // Load the index before searching
    await mossClient.loadIndex(indexName);

    // Search the index
    const result = await mossClient.query(indexName, "How do I return a damaged product?", {
      topK: 3,
    });

    // Display results
    console.log(`Query: ${result.query}`);
    result.docs.forEach((match) => {
      console.log(`Score: ${match.score.toFixed(4)}`);
      console.log(`ID: ${match.id}`);
      console.log(`Text: ${match.text}`);
      console.log("---");
    });
  } finally {
    // Release the client's underlying resources once you're done with it
    await mossClient.close();
  }
}

main().catch(console.error);
```

To use a host-managed stable id for MAD billing while retaining Moss's own
device UUID for correlation:

```typescript
const mossClient = new MossClient("project", "key", {
  identity: { deviceId: "host-installation-id", userId: "optional-user-id" },
});
```

`deviceId` is billable. `userId` is optional and non-billable. Telemetry also
includes Moss's file-backed UUID as `mossDeviceId`; without a host id, both
device fields contain that Moss UUID.

## Telemetry

The SDK always sends usage telemetry to the Moss cloud, and there is no option
to turn it off. It sends event types, your project id, index names, query and
document counts, query latencies, SDK and model versions, and a device id: a
random UUID stored on the device, or the `identity.deviceId` you supply, plus
`identity.userId` when you set one. Telemetry never includes query text,
document text, metadata, embeddings or file paths. Document text and embeddings
leave the device only when you create, add to or push an index in the cloud.

See [Telemetry](https://docs.moss.dev/docs/reference/telemetry) for every field and when it is sent.

## Resource cleanup

`MossClient` and sessions returned by `client.session(...)` hold native resources that must be released explicitly. Call `close()` on each one when you are done with it, in a `finally` block or equivalent. `close()` is idempotent, so it is safe to call more than once.

`client.close()` also closes every live session created from that client. Closing a session individually first is fine; `close()` is idempotent on both.

On Node 24 and later, both `MossClient` and sessions implement `Symbol.asyncDispose`, so you can use `await using` instead of a manual `try/finally`:

```typescript
await using mossClient = new MossClient("your-project-id", "your-project-key");
// mossClient.close() is called automatically when it goes out of scope
```

## 🔥 Example Use Cases

- Smart knowledge base search
- Realtime Voice AI agents
- Personal note-taking search
- Private in-app AI features (recommendations, retrieval)
- Local semantic search in edge devices, AR/VR, mobile apps

## 🧠 Providing custom embeddings

Already using your own embedding model? Supply vectors directly when managing indexes:

```typescript
const documents = [
  {
    id: "doc-1",
    text: "Attach a caller-provided embedding",
    embedding: myEmbeddingModel("doc-1"),
  },
  {
    id: "doc-2",
    text: "Fallback to the built-in model when the field is omitted.",
  },
];

await mossClient.createIndex("custom-embeddings", documents);

await mossClient.loadIndex("custom-embeddings");

const results = await mossClient.query("custom-embeddings", "", {
  embedding: myEmbeddingModel("query"),
  topK: 10,
});
```

Leaving `modelId` undefined defaults to `moss-minilm`. You can still pass `{ modelId: "moss-mediumlm" }` or another supported identifier if you want the service to generate embeddings for documents without the optional `embedding` field.

> **Normalize your vectors.** Moss does not normalize caller-provided embeddings, so
> rankings match cosine similarity only when document and query vectors are unit
> length (L2-normalized). Hosted embedding APIs such as OpenAI return normalized
> vectors already; local models often do not. Un-normalized vectors still return
> results, but the order can differ from what you would compute with cosine similarity.

### Foundation model identity

Moss generates local query embeddings for a foundation-model index only when
the service supplies the exact immutable model artifact identity used to build
that index. This prevents a query from being embedded with different model
bytes than the stored document vectors.

Fresh local sessions using `moss-minilm`, `moss-mediumlm`, or `moss-litelm`
bind that model's official current artifact automatically before model warmup.
Caller-supplied artifact identities are validated and kept, while custom models
are never auto-bound. `saveToDisk` records the exact model id, artifact version,
and manifest SHA-256, so the same session can be restored and queried with raw
text:

```typescript
const first = await mossClient.session("memory");
await first.addDocs([{ id: "refund", text: "Customer requested a refund" }]);
await first.saveToDisk(cachePath);
await first.close();

const restored = await mossClient.session("memory");
await restored.loadFromDisk(cachePath);
const results = await restored.query("refund");
```

Without `cachePath`, `saveToDisk()` and `loadFromDisk()` use `sessions/<project id>/`
under the first of these that is set:

1. the client's `cachePath` option (`new MossClient(id, key, { cachePath })`)
2. the `MOSS_SESSION_CACHE_PATH` environment variable, which only session snapshots
   read: the index cache and the model cache ignore it
3. `moss` in the default cache directory: `~/.cache/moss` on macOS and Linux,
   `%LOCALAPPDATA%\moss` on Windows

A relative `cachePath` resolves against the current working directory, and `~` is not expanded.

Session caches created by older SDKs without an artifact version and manifest
SHA-256 load as `custom` sessions through the legacy fail-closed path. Their raw
text queries require an explicit caller-generated embedding. Rebuild those
caches from their source documents with the current SDK, then save them again
so the automatically bound foundation identity is persisted.

Older indexes without that identity still load and remain queryable, but the
query must include a caller-generated vector of the correct dimension:

```typescript
const results = await mossClient.query("legacy-index", "search text", {
  embedding: myEmbeddingModel("search text"),
  topK: 10,
});
```

If the vector is omitted, the query fails closed with an error stating that an
explicit query embedding is required. Moss does not silently fall back to an
unverified local model or send the query to the cloud.

## Offline-tolerant load

With a `cachePath` set and a snapshot already on disk, a `loadIndex` whose cloud
metadata check fails on a transport error (unreachable network, timeout) serves
the cached snapshot instead of failing, and starts a refresh poller so the index
catches up when the cloud returns. A real "index not found" (404) still fails,
so a deleted index does not come back from cache.

A load served this way opens the index, but a built-in embedding model cannot be
opened until the Moss cloud is reachable, so text queries with `alpha` above 0
fail until then. Keyword-only queries (`alpha: 0`) and queries that pass their
own embedding keep working.

```typescript
await mossClient.loadIndex("my-docs", { cachePath: "/var/cache/moss" });
```

## Multi-index search

Search several loaded indexes in one call and get the global top-k back, with
each result tagged by its source `indexName`. All indexes must be loaded
locally and share the same embedding model.

```typescript
const { loaded, failed } = await mossClient.loadIndexes(["products", "reviews"]);
if (loaded.length === 0) {
  throw new Error(`No indexes loaded: ${JSON.stringify(failed)}`);
}

const results = await mossClient.queryMultiIndex(
  loaded,
  "noise cancelling headphones",
  { topK: 5, alpha: 0.5 },
);
for (const doc of results.docs) {
  console.log(`[${doc.indexName}] ${doc.id}: ${doc.text} (score: ${doc.score.toFixed(3)})`);
}

await mossClient.unloadIndexes(loaded);
```

`alpha` works exactly as in `query` (default 0.8): `1.0` is embedding-only,
`0.0` is keyword-only, and anything in between blends both with Reciprocal
Rank Fusion. Keyword scoring runs each index's own BM25 and merges each index's
raw hits before fusion; because BM25 statistics stay per-corpus, cross-index
keyword ranking is approximate. `topK` (default 10) caps the merged result, not
each index, and `filter` applies to every index. `loadIndexes` is best-effort:
names that fail are reported in `failed` without rolling back the ones that
loaded.

## Web sources

POST the existing `/v1/manage` web-source actions and return typed results.
Poll `jobId` with `getJobStatus`. Set `MOSS_CLOUD_API_BASE_URL` to send manage calls
to a non-default host (defaults to `https://service.usemoss.dev`).

```typescript
const created = await mossClient.createWebSource(
  "https://docs.example.com",
  "knowledge-base",
  { maxPages: 200, refreshCadence: "weekly" },
);
await mossClient.getJobStatus(created.jobId);

const sources = await mossClient.listWebSources("knowledge-base");
const source = await mossClient.getWebSource(created.id);
const updated = await mossClient.updateWebSource(created.id, {
  refreshCadence: "daily",
});
// updated.jobId is set when resync: true enqueued a crawl.
const resync = await mossClient.resyncWebSource(created.id);
const deleted = await mossClient.deleteWebSource(created.id);
// deleted.purgeJobId is set when a purge was enqueued.
```

## Metadata filtering

You can pass a metadata filter in `query` options after loading an index locally:

```typescript
const results = await mossClient.query("my-docs", "running shoes", {
  topK: 5,
  alpha: 0.6,
  filter: {
    $and: [
      { field: "category", condition: { $eq: "shoes" } },
      { field: "price", condition: { $lt: "100" } },
    ],
  },
});
```

## Inference

`MossInference` answers OpenAI's `responses.create`, with the arguments and
return shapes of OpenAI's Responses API, through the Moss inference gateway. The
gateway searches the `indexes` you pass and adds what it finds to the prompt, so
code written for OpenAI swaps its client for `MossInference` and adds `indexes`.
It also runs [browser tasks](#browser-tasks).

```typescript
import { MossInference } from "@moss-js/moss";

const client = new MossInference("your-project-id", "your-project-key");

const stream = await client.responses.create({
  input: "Do you ship to Canada?",
  indexes: ["faq"],
  stream: true,
});
for await (const event of stream) {
  if (event.type === "response.output_text.delta") process.stdout.write(event.delta ?? "");
}
```

`model` is optional and defaults to `"moss"`, Moss's own model. Without
`stream: true` the call reads the whole stream and returns the `Response` of its
last event, whose `output_text` joins the text of its messages:

```typescript
const response = await client.responses.create(
  {
    instructions: "Answer in one sentence.",
    input: "Do you ship to Canada?",
    indexes: ["faq"],
  },
  { timeout: 30_000 },
);
console.log(response.output_text);
```

With `MOSS_PROJECT_ID` and `MOSS_PROJECT_KEY` set,
`inference.responses.create(...)` takes the same arguments without a client.

`input` is a string, or the conversation so far as a list of items: messages
such as `{ role: "user", content: "Hi" }`, and the `output` items of earlier
responses. Moss stores nothing, so send the whole conversation each time.
`store` is ignored, and `previous_response_id`, `background`, `include` and
OpenAI's built-in tools, such as `web_search`, are refused with
`invalid_request_error` and the `errorCode` `unsupported_parameter`. Other
OpenAI parameters, such as `temperature`, `text: { format }` for structured
output or `reasoning: { effort: "low" }`, reach the gateway unchanged.

`apiKey` is optional: your own OpenAI, Anthropic or Google key, for a vendor
model such as `gpt-4o-mini`. `moss` ignores it, and a vendor model without one
is refused. Set it on the client, or pass it with one call, where it wins over
the client's:

```typescript
const keyed = new MossInference("your-project-id", "your-project-key", {
  apiKey: "your-openai-key",
});
const reply = await keyed.responses.create(
  { model: "gpt-4o-mini", input: "Hi" },
  { apiKey: "your-other-openai-key" },
);
```

The other client options are `timeout` for each whole call (no limit by
default), `idleTimeout` for the longest wait for response headers or for more of
the body (120 000 ms by default, `null` for none), `maxRetries` and `headers`.
Node's built-in `fetch` also ends a silence of 300 000 ms, unless its global
dispatcher allows more. Each call takes `apiKey`, `signal`, `timeout`,
`idleTimeout`, `maxRetries` and `headers`, which replace or add to the client's
for that call. Neither `headers` can set `Host`, `Content-Length` or
`Transfer-Encoding`.

`maxRetries` (2 by default, `0` for none) sends a call again when the connection
fails, or when the gateway answers 408, 409, 429 or 5xx before the stream
starts, after a `Retry-After` of up to 60 s, else a backoff of 0.5 s doubling
up to 8 s, within `timeout`. `retrieve: false` or `indexes: []` skips the
search, and leaving `indexes` out searches every index. Moss can answer an
identical request from its reply cache; `cache: false` always asks the model.
`stream.requestId` and a response's `requestId`, which `JSON.stringify` leaves
out, hold the response's `X-Moss-Request-Id`.

To call another gateway, set `MOSS_INFERENCE_URL` to
its base URL, up to and including `/v1`, before you build the client. A
`baseURL` or `baseUrl` option, on the client or a call, is an error.

A stream ends after `response.completed`, or after `response.incomplete` for a
response cut by `max_output_tokens`, whose `status` is then `incomplete`, with
the reason in `incomplete_details`. Leaving the `for await` loop early, or
calling `stream.controller.abort()`, closes the connection, stops the model and
ends the loop quietly. An abort with any other reason, such as the
`TimeoutError` of `AbortSignal.timeout()`, throws that reason. Without
`stream: true`, an abort rejects with the signal's reason, an `AbortError` for a
plain `abort()`. Every other failure throws `InferenceError` with `status`,
`type` and a Moss `code` that `isMossError` accepts, including a
`response.failed` event, a stream that ends before its last event
(`incomplete_stream`), a broken connection (`connection_error`) and a timeout
(`timeout`). It also carries the gateway's `errorCode`, the response's
`requestId` and, for a `429` or another error that sends `Retry-After`,
`retryAfter` in milliseconds. The client does not follow redirects.

### Tool calls

`tools`, `tool_choice` and `parallel_tool_calls` are sent as given. A function
tool is flat, as in OpenAI's Responses API. Each call comes as a
`function_call` item of `output`, which keeps every field the model sent, such
as Gemini's `extra_content` with the thought signature Gemini 3 needs back.
After streaming the text, `finalResponse()` gives the whole response. Push its
`output` items onto `input` unchanged, add one `function_call_output` item per
call, and call again:

```typescript
import type { FunctionTool, ResponseInputItem } from "@moss-js/moss";

const input: ResponseInputItem[] = [{ role: "user", content: "Is the EQB jacket in stock?" }];
const tools: FunctionTool[] = [
  {
    type: "function",
    name: "check_stock",
    parameters: { type: "object", properties: { sku: { type: "string" } } },
  },
];
for (;;) {
  const stream = await client.responses.create({ input, tools, stream: true });
  for await (const event of stream) {
    if (event.type === "response.output_text.delta") process.stdout.write(event.delta ?? "");
  }
  const { output } = await stream.finalResponse();
  input.push(...output);
  const calls = output.filter((item) => item.type === "function_call");
  if (calls.length === 0) break;
  for (const call of calls) {
    const { sku } = JSON.parse(call.arguments);
    input.push({ type: "function_call_output", call_id: call.call_id, output: await checkStock(sku) });
  }
}
```

`finalResponse()` reads what the loop has not read. If the stream was closed
before its last event, it rejects, so it never returns part of a response.

### MCP servers

An `McpServer` entry in `tools` lets the gateway call that server's tools for
the model during the response. Each call comes as an `mcp_call` item, in
`response.output_item.added` when it starts and `response.output_item.done`
when it ends:

```typescript
import type { McpServer } from "@moss-js/moss";

const crm: McpServer = {
  type: "mcp",
  server_label: "crm",
  server_url: "https://mcp.example.com/mcp",
  headers: { Authorization: "Bearer your-crm-token" },
};
const stream = await client.responses.create({
  input: "Where is order A1?",
  tools: [crm],
  stream: true,
});
for await (const event of stream) {
  if (event.type === "response.output_item.done" && event.item?.type === "mcp_call") {
    console.log(event.item.server_label, event.item.name, event.item.output ?? event.item.error);
  } else if (event.type === "response.output_text.delta") {
    process.stdout.write(event.delta ?? "");
  }
}
```

An `mcp_call` item has the `server_label`, `name` and `arguments` of the call,
and once it ended its `status`, `output` or `error`, and `duration_ms`. Without
`stream: true`, the same items are in the response's `output`, in order.
Sending the `output` items back in `input`, `mcp_call` items included, gives the
model the earlier tool results. A response with tools can run for a few minutes.

| `status` | `type` | `errorCode` | When |
| --- | --- | --- | --- |
| 403 | `permission_error` | `mcp_not_enabled` | MCP is switched off on the gateway |
| 429 | `capacity` | `mcp_loops_busy` | The gateway is busy; retry after `retryAfter` |
| 400, 424 | `mcp_error` | `mcp_server_error` | The URL was refused, or the server failed |
| 400 | `invalid_request_error` | (none) | A bad `tools` entry, or a label or tool name used twice |

After an `mcp_call` item every failure has `errorCode` `failed_after_tool_call`,
and the SDK never retries. Nor does it retry any stream that fails after it
started. The tool may have changed data, and so may a call you abort or time out
after such an item, so do not replay such a call blindly.

### Browser tasks

`client.tasks` gives an agent a goal to reach in a browser, within time and
dollar limits. `run` creates the task and resolves once it is `completed`,
`failed` or `cancelled`:

```typescript
interface Flight {
  airline: string;
  price: number;
}

const done = await client.tasks.run<Flight>(
  {
    goal: "Find the cheapest nonstop flight from SFO to JFK next Friday.",
    environment: { type: "browser", start_url: "https://www.google.com/travel/flights" },
    output_schema: {
      type: "object",
      properties: { airline: { type: "string" }, price: { type: "number" } },
      required: ["airline", "price"],
    },
    limits: { max_runtime_seconds: 360, max_cost_usd: 0.25 },
  },
  { timeout: 600_000 },
);
if (done.status === "completed") {
  console.log(done.result?.output?.price, done.verification?.passed, done.usage?.cost_usd);
} else {
  console.log(done.status, done.error?.code, done.error?.message);
}
```

A task runs for minutes. To keep its id first, `create` returns the `queued`
task at once, and `wait` polls it until it ends:

```typescript
const task = await client.tasks.create({ goal: "Find the library's opening hours.", environment: { type: "browser" } });
const finished = await client.tasks.wait(task.id);
```

Only the fields you pass are sent. The gateway picks the `model`, `effort` and
limits you leave out, and refuses a field it does not know. `model` is a name of
the Moss catalog, sent as is. With `output_schema` the gateway checks the
answer, and `verification.passed` is false, with `problems`, when it does not
match. `result` comes back either way. The type argument types
`result.output`, and the SDK does not check it. `usage` holds the model calls,
tokens and `cost_usd`, plus any other field the gateway sends, such as
`browser_minutes`.

`run` and `wait` resolve on a `failed` task too, so read `status` and `error`.
Their `timeout` limits the wait and is off by default. Past it, they throw a
`timeout` InferenceError and the task goes on, so wait again or cancel it. They
poll every `pollInterval`, 2000 ms by default. `signal` aborts them. Once the
task exists, their errors carry its `taskId`, so a task that `run` created can
still be read or cancelled. `cancel` stops a queued task at once. A running
task comes back with `cancel_requested: true` and ends `cancelled` soon after.

`trace` resolves to the agent's step-by-step record once `trace_available` is
true, and rejects with `not_found_error` before. `files.list` lists the
screenshots and output files once the task ends, and `files.content` resolves
to a file's bytes and `contentType`. The SDK never opens or renders a file. The
gateway removes the trace and files at the task's `files_expire_at`, 7 days
after it ends:

```typescript
import { writeFile } from "node:fs/promises";
import { basename } from "node:path";

for (const file of (await client.tasks.files.list(done.id)).data) {
  const { data } = await client.tasks.files.content(done.id, file.path);
  await writeFile(basename(file.path), data);
}
```

Each call takes the options of `responses.create`, and retries as it does.
`create` and `run` also take `apiKey`, and send only that call's key as
`X-Moss-Provider-Key`, for the task's model calls; see the pricing docs. Tasks
never use the client's `apiKey`, and the other calls never send a key.
`create` sends an
`Idempotency-Key`, a new one each call or the one in that call's `headers`, and
the same one on every retry. The gateway answers a repeated key with the same
body, within 24 hours, with the task it created, so a retried create never
starts a second task. To retry a create yourself, pass your own key. A key in
the client's `headers` is not used. `inference.tasks` is the `tasks` of a client
built from the environment, and reading it throws when the credentials are
missing.

| `status` | `type` | `errorCode` | When |
| --- | --- | --- | --- |
| 400 | `invalid_request_error` | `invalid_request_error` | A field or value the gateway refuses |
| 400 | `invalid_request_error` | `model_not_found` | A model the gateway does not serve |
| 403 | `permission_error` | `tasks_not_enabled` | Tasks are not enabled for the project |
| 404 | `not_found_error` | `not_found_error` | No such task in the project, no trace yet, or no such file |
| 429 | `rate_limit_error` | `too_many_queued_tasks` | Too many queued tasks; retry after `retryAfter` |
| 409 | `invalid_request_error` | `task_not_finished` | The files of a task that has not ended |
| 410 | `invalid_request_error` | `files_expired` | The trace or files after `files_expire_at` |
| 422 | `invalid_request_error` | `idempotency_key_reused` | A create's key was sent before with another body |
| 503 | `server_error` | `server_error` | Tasks are not enabled on the gateway |
| 503 | `server_error` | `tasks_unavailable` | Tasks cannot run now; a create retries after `retryAfter` |

## 📄 License

This package is licensed under the [PolyForm Shield License 1.0.0](./LICENSE.txt).

- ✅ Free for any use, including production and commercial use.
- ❌ Not permitted: providing a product that competes with Moss.
- 📩 For commercial licenses, contact: <contact@inferedge.dev>

## 📬 Contact

For support, commercial licensing, or partnership inquiries, contact us: [contact@inferedge.dev](mailto:contact@inferedge.dev)

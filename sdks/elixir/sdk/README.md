# Moss client library for Elixir

`moss` enables **private, on-device semantic search** in your Elixir applications with cloud storage capabilities.

Built for developers who want **instant, memory-efficient, privacy-first AI features** with seamless cloud integration.

## Features

- **On-Device Vector Search** - Sub-millisecond retrieval with zero network latency
- **Semantic, Keyword & Hybrid Search** - Embedding search blended with keyword matching
- **Cloud Storage Integration** - Automatic index synchronization with cloud storage
- **Multi-Index Support** - Manage multiple isolated search spaces
- **Privacy-First by Design** - Computation happens locally. Indexes sync to the cloud, and usage telemetry is sent (see [Telemetry](#telemetry))
- **High-Performance Rust Core** - Built on optimized Rust NIFs for maximum speed
- **Custom Embedding Overrides** - Provide your own document and query vectors when you need full control

## Installation

```elixir
# mix.exs
defp deps do
  [{:moss, "~> 1.0"}]
end
```

## Quick Start

```elixir
alias Moss.{Client, DocumentInfo}

# Initialize search client with project credentials
{:ok, client} = Client.new("your-project-id", "your-project-key")

# Prepare documents to index
documents = [
  %DocumentInfo{
    id: "doc1",
    text: "How do I track my order? You can track your order by logging into your account.",
    metadata: %{"category" => "shipping"}
  },
  %DocumentInfo{
    id: "doc2",
    text: "What is your return policy? We offer a 30-day return policy for most items.",
    metadata: %{"category" => "returns"}
  },
  %DocumentInfo{
    id: "doc3",
    text: "How can I change my shipping address? Contact our customer service team.",
    metadata: %{"category" => "support"}
  }
]

# Create an index with documents (syncs to cloud)
{:ok, _} = Client.create_index(client, "faqs", documents)  # Defaults to moss-minilm

# Load the index (from cloud or local cache)
{:ok, _} = Client.load_index(client, "faqs")

# Search the index
{:ok, result} = Client.query(client, "faqs", "How do I return a damaged product?", top_k: 3, alpha: 0.6)

# Display results
IO.puts("Query: #{result.query}")

for doc <- result.docs do
  IO.puts("Score: #{Float.round(doc.score, 4)}")
  IO.puts("ID: #{doc.id}")
  IO.puts("Text: #{doc.text}")
  IO.puts("---")
end
```

## Example Use Cases

- Smart knowledge base search with cloud backup
- Realtime Voice AI agents with persistent indexes
- Personal note-taking search with sync across devices
- Private in-app AI features with cloud storage
- Local semantic search in edge devices with cloud fallback

## Available Models

- `moss-minilm`: Lightweight model optimized for speed and efficiency
- `moss-mediumlm`: Balanced model offering higher accuracy with reasonable performance

## Getting Started

### Prerequisites

- Elixir 1.15 or higher
- OTP 26 or higher
- Valid InferEdge project credentials

### Environment Setup

1. **Install the package:**

```elixir
# mix.exs
defp deps do
  [{:moss, "~> 1.0"}]
end
```

2. **Get your credentials:**

Sign up at [Moss Platform](https://portal.usemoss.dev) to get your `project_id` and `project_key`.

3. **Set up environment variables (optional):**

```bash
export MOSS_PROJECT_ID="your-project-id"
export MOSS_PROJECT_KEY="your-project-key"
```

### Basic Usage

```elixir
{:ok, client} = Moss.Client.new("your-project-id", "your-project-key")

# Create and populate an index
documents = [
  %Moss.DocumentInfo{id: "1", text: "Python is a programming language"},
  %Moss.DocumentInfo{id: "2", text: "Machine learning with Python is popular"}
]

{:ok, _} = Moss.Client.create_index(client, "my-docs", documents)
{:ok, _} = Moss.Client.load_index(client, "my-docs")

# Search
{:ok, results} = Moss.Client.query(client, "my-docs", "programming language", alpha: 1.0)

for doc <- results.docs do
  IO.puts("#{doc.id}: #{doc.text} (score: #{Float.round(doc.score, 3)})")
end
```

### Hybrid Search Controls

`alpha` lets you decide how much weight to give semantic similarity versus keyword relevance when running `query`:

```elixir
# Pure keyword search
Client.query(client, "my-docs", "programming language", alpha: 0.0)

# Mixed results (default 0.8, semantic heavy)
Client.query(client, "my-docs", "programming language")

# Pure embedding search
Client.query(client, "my-docs", "programming language", alpha: 1.0)
```

Pick any value between 0.0 and 1.0 to tune the blend for your use case.

### Multi-Index Search

Search several loaded indexes in one call and get the global top-k back, with
each result tagged by its source `index_name`. All indexes must be loaded
locally and share the same embedding model.

```elixir
{:ok, %Moss.LoadIndexesResult{loaded: loaded, failed: failed}} =
  Moss.Client.load_indexes(client, ["products", "reviews"])

if loaded == [], do: raise("No indexes loaded: #{inspect(failed)}")

{:ok, results} =
  Moss.Client.query_multi_index(client, loaded, "noise cancelling headphones", top_k: 5, alpha: 0.5)

for doc <- results.docs do
  IO.puts("[#{doc.index_name}] #{doc.id}: #{doc.text} (score: #{Float.round(doc.score, 3)})")
end

:ok = Moss.Client.unload_indexes(client, loaded)
```

`:alpha` works exactly as in `query/4` (default 0.8): `1.0` is embedding-only,
`0.0` is keyword-only, and anything in between blends both with Reciprocal Rank
Fusion. Keyword scoring runs each index's own BM25 and merges each index's raw
hits before fusion, so cross-index keyword ranking is approximate. `:top_k`
(default 10) caps the merged result, not each index, and `:filter` applies to
every index. `load_indexes/3` is best-effort: names that fail are reported in
`failed` without rolling back the ones that loaded.

### Metadata Filtering

You can pass a metadata filter directly to `query` after loading an index locally:

```elixir
{:ok, result} = Moss.Client.query(
  client,
  "my-docs",
  "running shoes",
  top_k: 5,
  alpha: 0.6,
  filter: %{
    "$and" => [
      %{"field" => "category", "condition" => %{"$eq" => "shoes"}},
      %{"field" => "price", "condition" => %{"$lt" => "100"}}
    ]
  }
)
```

Supported operators: `$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`, `$in`, `$nin`, `$near`

Logical combinators: `$and`, `$or`

### Custom Embeddings

Already using your own embedding model? Supply vectors directly when managing indexes and queries:

```elixir
{:ok, client} = Moss.Client.new("your-project-id", "your-project-key")

documents = [
  %Moss.DocumentInfo{
    id: "doc-1",
    text: "Attach a caller-provided embedding.",
    embedding: my_embedding_model("doc-1")
  },
  %Moss.DocumentInfo{
    id: "doc-2",
    text: "Fallback to the built-in model when the field is omitted.",
    embedding: my_embedding_model("doc-2")
  }
]

{:ok, _} = Moss.Client.create_index(client, "custom-embeddings", documents)
{:ok, _} = Moss.Client.load_index(client, "custom-embeddings")

{:ok, results} = Moss.Client.query(
  client,
  "custom-embeddings",
  "query text",
  embedding: my_embedding_model("query text"),
  top_k: 10
)

IO.puts("#{hd(results.docs).id}: #{hd(results.docs).score}")
```

### Sessions

For real-time indexing during live workflows (voice AI agents, chat), use sessions:

```elixir
{:ok, client} = Moss.Client.new("project-id", "project-key")
{:ok, session} = Moss.Client.session(client, "session-abc")

docs = [
  %Moss.DocumentInfo{id: "turn-1", text: "Customer: I need to cancel my subscription"},
  %Moss.DocumentInfo{id: "turn-2", text: "Agent: I can help with that. Can I ask why?"}
]

{:ok, _} = Moss.Session.add_docs(session, docs)
{:ok, result} = Moss.Session.query(session, "subscription cancellation", top_k: 2)

# Push session index to cloud when done
{:ok, _} = Moss.Session.push_index(session)
```

`Moss.Session.save_to_disk/2` writes a session under `<cache_path>/<name>/`, and
`Moss.Session.load_from_disk/3` restores it into a later session with the same
name. Open that session with `auto_load_on_init: false`: it then skips the cloud
index load that the snapshot would replace, so the restore downloads no index:

```elixir
:ok = Moss.Session.save_to_disk(session, "/var/cache/moss")
:ok = Moss.Session.close(session)

{:ok, restored} = Moss.Client.session(client, "session-abc", auto_load_on_init: false)
{:ok, _doc_count} = Moss.Session.load_from_disk(restored, "/var/cache/moss")
```

Without `cache_path`, `Moss.Session.save_to_disk(session)` and
`Moss.Session.load_from_disk(session)` use `sessions/<project id>/` under the first of these
that is set:

1. the client's `:cache_path` (`Moss.Client.new(id, key, cache_path: ...)`)
2. the `MOSS_SESSION_CACHE_PATH` environment variable, as set when the VM started
   (`System.put_env/2` does not reach the native core, so set `:cache_path` from inside the app).
   Only session snapshots read it: the index cache and the model cache ignore it.
3. `moss` in the default cache directory: `~/.cache/moss` on macOS and Linux,
   `%LOCALAPPDATA%\moss` on Windows

A relative `cache_path` resolves against the current working directory, and `~` is not expanded.

A snapshot that an older core saved for a built-in model has no model artifact
identity. `load_from_disk/3` rebuilds it for a session opened with the same model,
re-embedding the stored documents with the current model and saving the snapshot
back, which needs the cloud for the model. Pass `rebuild_legacy: false` to load
such a snapshot as a custom-model session instead.

## Inference

`Moss.Inference` is a client for OpenAI's Responses API, answered by Moss inference
at `https://inference.moss.dev/v1`. Moss searches your indexes, adds what it finds to the prompt
and streams the model's response. `params` is the OpenAI request body, so code written for
OpenAI only adds `:indexes`.

```elixir
alias Moss.Inference.Responses

client = Moss.Inference.new("project-id", "project-key")

# Streamed: events arrive as the model writes
params = %{input: "Do you ship to Canada?", stream: true}
{:ok, stream} = Responses.create(client, params, indexes: ["faq"])

for %{"type" => "response.output_text.delta", "delta" => delta} <- stream do
  IO.write(delta)
end

# Not streamed: the whole response
params = %{instructions: "Answer in one sentence.", input: "Do you ship to Canada?"}
{:ok, response} = Responses.create(client, params, indexes: ["faq"])
IO.puts(response["output_text"])
```

`model` defaults to `"moss"`, Moss's own model.
`input` is a string, or the conversation so far as a list of items: input messages such as
`%{role: "user", content: "Hi"}`, and the `"output"` items of earlier responses. Moss stores nothing,
so send the whole conversation each time. `store` is ignored, and `previous_response_id`,
`background`, `include` and OpenAI's built-in tools, such as `web_search`, are refused with
`invalid_request_error` and the code `unsupported_parameter`. Other OpenAI parameters, such as
`temperature`, `text: %{format: ...}` for structured output or `reasoning: %{effort: "low"}`,
reach the gateway unchanged.
`Moss.Inference.new/3` checks the credentials and options and raises `Moss.Inference.Error`
for a bad one. It takes `:api_key`, `:timeout` (milliseconds for a whole call, default
`:infinity`), `:idle_timeout` (milliseconds Moss may stay silent, default `120_000`) and
`:max_retries` (retries of a failed connection or a 408, 409, 429 or 5xx reply, default `2`).
A call takes `:api_key`, `:timeout`, `:idle_timeout` and `:max_retries` too, over the client's,
plus `retrieve: false` or `indexes: []` to skip the search. A call's options go in its last
argument, and `params` that hold one return an error.
Moss can answer an identical request from its reply cache; `cache: false` always asks the model.

`:api_key` is optional: your own OpenAI, Anthropic or Google key, for a vendor model such as
`gpt-4o-mini`. `moss` ignores it, and a vendor model without one is refused. An empty key, or
one that starts or ends with a space, is an error, and no key appears in an error or in `inspect/2`.

```elixir
# A vendor model, with your own OpenAI key for this call
api_key = System.fetch_env!("OPENAI_API_KEY")
params = %{model: "gpt-4o-mini", input: "Do you ship to Canada?"}
{:ok, response} = Responses.create(client, params, api_key: api_key)
```

Events and responses are maps with OpenAI's field names as string keys. A stream ends after
`response.completed`, or `response.incomplete` for a response cut by `max_output_tokens`, whose
`"status"` is then `"incomplete"`, and that last event's `"response"` is the whole response.
`stream.request_id` and `response["request_id"]` hold the reply's `X-Moss-Request-Id`, else `nil`.

A failure before the response starts returns `{:error, %Moss.Inference.Error{}}` with `status`,
`type` and `message`, plus the gateway's `code`, the reply's `request_id` and an error reply's
`retry_after` in milliseconds, when they are known. A stream raises `Moss.Inference.Error` if
the response fails after it starts, as a `response.failed` or `error` event does. Read a stream in
the process that created it. Stopping early, for example with `Enum.take/2`, closes the connection
and stops the model. `Moss.Inference.ResponseStream.close/1` does the same from any process, and
the stream then ends without an error.

Calls reuse idle connections, from any process. A reply read to its end gives its connection
back, and a stream that stops early or fails closes its own. A pooled connection found closed
is replaced before the call is written to it, and a stream that fails after it started is never
retried. The pool keeps up to 100 idle connections, each for at most 4 seconds.

To call another gateway, set `MOSS_INFERENCE_URL` to its base URL,
such as `https://gateway.example.com/v1`, and `/responses` goes after it. `Moss.Inference.new/3`
reads it, and raises an error for a value that is not an `http` or `https` URL with a host and no
user info, query or fragment.

### Tool calls

`tools`, `tool_choice` and `parallel_tool_calls` go in `params` as in OpenAI's Responses API, where
a function tool is flat. Your code runs the tools. Each call comes as a `"function_call"` item in the
response's `"output"`. Put the output items back into `input` as they are, then one
`"function_call_output"` item per call. An item keeps every field the model sent, such as Gemini's
`extra_content`, so it goes back unchanged.

```elixir
defmodule Orders do
  alias Moss.Inference.Responses

  @lookup %{type: "function", name: "lookup_order", parameters: %{type: "object"}}

  def answer(client, input) do
    {:ok, response} = Responses.create(client, %{input: input, tools: [@lookup]})

    results =
      for %{"type" => "function_call"} = call <- response["output"] do
        output = lookup_order(call["arguments"])
        %{type: "function_call_output", call_id: call["call_id"], output: output}
      end

    if results == [],
      do: response["output_text"],
      else: answer(client, input ++ response["output"] ++ results)
  end
end

Orders.answer(client, [%{role: "user", content: "Where is order A1?"}])
```

### MCP servers

A `Moss.Inference.McpServer` in `tools` lets Moss call that server's tools itself. Each call comes
as an `"mcp_call"` item, in `response.output_item.added` when it starts and
`response.output_item.done` when it ends. It has the `"server_label"`, `"name"` and `"arguments"`
of the call, and once it ended its `"status"`, `"output"` or `"error"`, and `"duration_ms"`.
Without `stream`, the same items are in the response's `"output"`, in order. Sent back in `input`
with the rest of `"output"`, they give the model the earlier tool results. A turn with tools can
run for a few minutes.
`inspect/2` leaves out `server_url` and `headers`.

```elixir
crm = %Moss.Inference.McpServer{
  server_label: "crm",
  server_url: "https://mcp.example.com/mcp",
  headers: %{"Authorization" => "Bearer " <> System.fetch_env!("CRM_TOKEN")}
}

params = %{input: "Where is order A1?", tools: [crm], stream: true}
{:ok, stream} = Responses.create(client, params)

for %{"type" => "response.output_item.done", "item" => %{"type" => "mcp_call"} = call} <- stream do
  IO.puts("#{call["server_label"]}.#{call["name"]}: #{call["output"]}")
end
```

| `status` | `type` | `code` | When |
| --- | --- | --- | --- |
| 403 | `permission_error` | `mcp_not_enabled` | MCP is switched off on the gateway |
| 429 | `capacity` | `mcp_loops_busy` | The gateway is busy; retry after `retry_after` |
| 400, 424 | `mcp_error` | `mcp_server_error` | The URL was refused, or the server failed to connect or list its tools |
| 400 | `invalid_request_error` | `nil` | A bad `tools` entry, or a `server_label` or tool name used twice |

After an `"mcp_call"` item every failure has code `failed_after_tool_call`, and the SDK never retries:
a tool may have changed data, as it may in a call you stop after one, so never resend either blindly.

## Telemetry

`moss` always sends usage telemetry to the Moss cloud. See [Telemetry](https://docs.moss.dev/docs/reference/telemetry) for what it contains and when it is sent.

## API Reference

Every public module and function is documented on [HexDocs](https://hexdocs.pm/moss).

## License

This package is licensed under the [PolyForm Shield License 1.0.0](./LICENSE.txt).

- Free for any use, including production and commercial use.
- Not permitted: providing a product that competes with Moss.
- For commercial licenses, contact: <contact@moss.dev>

## Contact

For support, commercial licensing, or partnership inquiries: [contact@moss.dev](mailto:contact@moss.dev)

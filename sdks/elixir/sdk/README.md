# Moss client library for Elixir

`moss` enables **private, on-device semantic search** in your Elixir applications with cloud storage capabilities.

Built for developers who want **instant, memory-efficient, privacy-first AI features** with seamless cloud integration.

## Features

- **On-Device Vector Search** - Sub-millisecond retrieval with zero network latency
- **Semantic, Keyword & Hybrid Search** - Embedding search blended with keyword matching
- **Cloud Storage Integration** - Automatic index synchronization with cloud storage
- **Multi-Index Support** - Manage multiple isolated search spaces
- **Privacy-First by Design** - Computation happens locally, only indexes sync to cloud
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
- Valid Moss project credentials

### Environment Setup

1. **Install the package:**

```elixir
# mix.exs
defp deps do
  [{:moss, "~> 1.0"}]
end
```

2. **Get your credentials:**

Sign up at [Moss Platform](https://portal.moss.dev) to get your `project_id` and `project_key`.

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

## License

This package is licensed under the [BSD 2-Clause License](./LICENSE).

`moss` reports aggregated usage counts to Moss servers for billing. No document content is sent.

## Contact

For support, commercial licensing, or partnership inquiries: [contact@moss.dev](mailto:contact@moss.dev)

# Moss Roadmap

This is a living document. We update it as priorities shift based on community feedback and production learnings. If something here excites you, open an issue or PR — we move fast on contributions.

## Shipped

- [x] Python SDK (`inferedge-moss`) — async-first, type-safe
- [x] TypeScript SDK (`@inferedge/moss`) — full feature parity with Python
- [x] Built-in embedding models (`moss-minilm`)
- [x] **Hybrid search** — combine semantic search with BM25 keyword matching
- [x] Custom embedding support (bring your own OpenAI, Cohere, etc.)
- [x] Metadata filtering (`$eq`, `$and`, `$in`, `$near`)
- [x] Document management (add, upsert, get, delete)
- [x] LangChain integration
- [x] DSPy integration
- [x] Pipecat voice agent integration
- [x] LiveKit voice agent integration
- [x] Next.js example app
- [x] VitePress search plugin
- [x] Docker deployment examples (ECS/K8s patterns)
- [x] WebAssembly runtime — client-side semantic search in the browser, no server required

## In Progress

- [ ] **Benchmarks directory** — reproducible latency/throughput scripts comparing Moss vs Pinecone, Qdrant, and Chroma on standardized datasets
- [ ] **MCP server** — expose Moss as a Model Context Protocol server so any MCP-compatible AI tool (Claude, Cursor, Windsurf) can do semantic search
- [ ] **npm/PyPI package rename** — consolidating package names under the Moss brand
- [ ] **Vercel AI SDK integration** — retrieval provider for the Vercel AI SDK

## Next Up — Community Contributions Welcome

These are well-scoped and ready for contributors. Each one has (or will have) a corresponding GitHub issue with detailed instructions.

### New SDK Bindings

- [ ] **Swift bindings** — for iOS/macOS apps with on-device retrieval ([`good first issue`](https://github.com/usemoss/moss/labels/good%20first%20issue))
- [ ] **Go bindings** — for backend services and CLI tools ([`good first issue`](https://github.com/usemoss/moss/labels/good%20first%20issue))
- [ ] **Elixir bindings** — for Phoenix/LiveView apps ([`good first issue`](https://github.com/usemoss/moss/labels/good%20first%20issue))
- [ ] **Rust bindings** — for performance-critical pipelines ([`good first issue`](https://github.com/usemoss/moss/labels/good%20first%20issue))

### Framework Integrations

- [ ] **CrewAI** — Moss as a retrieval tool for CrewAI agents ([`good first issue`](https://github.com/usemoss/moss/labels/good%20first%20issue))
- [ ] **Haystack** — document store / retriever integration
- [ ] **AutoGen** — retrieval-augmented tool for AutoGen agents
- [ ] **LlamaIndex** — retriever and query engine integration
- [ ] **Semantic Kernel** — .NET/Python retrieval plugin

### Search Quality

- [ ] **Reranking support** — plug in cross-encoder rerankers (Cohere Rerank, bge-reranker, etc.) as a post-retrieval step
- [ ] **Multi-vector retrieval** — support ColBERT-style late interaction models

### Data Ingestion

- [ ] **Doc-parsing connectors** — ingest PDF, DOCX, HTML, and Markdown files directly into Moss indexes
- [ ] **Chunking strategies** — built-in text splitters (sentence, paragraph, recursive, semantic)
- [ ] **Web crawling** — crawl a URL and index the content

## Future

These are bigger bets we're exploring. They're directional, not committed — community input will shape what gets built.

### Local-First AI Stack

- [ ] **vLLM-based local inference + local search** — a fully local pipeline: your model, your embeddings, your search, your hardware. No API calls. This is a natural fit for the privacy-first voice AI use case and can meaningfully cut latency for on-premise deployments.
- [ ] **Ollama + Moss + Pipecat reference architecture** — an end-to-end fully local voice agent: Ollama for LLM inference, Moss for retrieval, Pipecat for real-time audio. A single `docker compose up` to run the entire stack.

### Evaluation & Quality

- [ ] **LLM-as-a-judge evaluation framework** — automated retrieval quality scoring using LLM judges. We want to lay the foundation and let the community decide the direction — what metrics matter, which judges to support, how to benchmark fairly.
- [ ] **Retrieval quality dashboard** — visualize query performance, relevance scores, and failure modes over time

### Browser & Edge

- [ ] **Edge runtime support** — run Moss in Cloudflare Workers, Deno Deploy, and Vercel Edge Functions

---

## How to Contribute

1. **Pick something from "Next Up"** — these are ready for PRs
2. **Check the [issues](https://github.com/usemoss/moss/issues)** — look for `good first issue` and `help wanted` labels
3. **Propose something new** — open an issue describing what you want to build. We're open to ideas that aren't on this list.
4. **Read the [Contributing Guide](CONTRIBUTING.md)** — fork, branch from `main`, PR

If you're unsure where to start, drop a message in [Discord](https://discord.gg/eMXExuafBR) and we'll point you in the right direction.

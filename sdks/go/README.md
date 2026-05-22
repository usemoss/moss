# Moss Go SDK

The Go SDK is currently implemented as a cloud-first, pure-Go client.

Current status:

- typed client and models
- cloud reads (`GetIndex`, `ListIndexes`, `GetDocs`, `DeleteIndex`)
- cloud query (`Query`)
- cloud mutations (`CreateIndex`, `AddDocs`, `DeleteDocs`, `GetJobStatus`)
- unit tests

Current limitations:

- no local `LoadIndex` / `UnloadIndex`
- no in-memory query runtime
- no local metadata-filtered query parity

The Go module itself lives under [`sdks/go/sdk/`](./sdk/).

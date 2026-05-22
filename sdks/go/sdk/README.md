# Moss client library for Go

`moss` provides a typed Go client for Moss cloud-backed semantic search workflows.

This first Go release is intentionally:

- pure Go
- cloud-first
- buildable from the public repository

## Features

- typed Go client and models
- cloud index creation and document mutation
- cloud index metadata and document reads
- cloud query with optional caller-provided embeddings
- env-gated live integration tests

## Current limitations

- no local `LoadIndex` / `UnloadIndex`
- no in-memory query runtime
- no local metadata filtering support

If you pass `QueryOptions.Filter`, the Go SDK returns an explicit error because
cloud-only query does not yet provide the same behavior as the local runtimes.

## Installation

From this repository, use the module at:

```go
github.com/usemoss/moss/sdks/go/sdk/moss
```

## Quick start

```go
package main

import (
	"context"
	"fmt"
	"log"

	"github.com/usemoss/moss/sdks/go/sdk/moss"
)

func main() {
	ctx := context.Background()

	client := moss.NewClient("your-project-id", "your-project-key")

	docs := []moss.DocumentInfo{
		{
			ID:   "doc-1",
			Text: "Refunds are processed within five to seven business days.",
			Metadata: map[string]string{
				"topic": "refunds",
			},
		},
		{
			ID:   "doc-2",
			Text: "Orders can be tracked from the account dashboard.",
			Metadata: map[string]string{
				"topic": "shipping",
			},
		},
	}

	result, err := client.CreateIndex(ctx, "support-docs", docs, nil)
	if err != nil {
		log.Fatal(err)
	}

	fmt.Println("created job:", result.JobID)

	search, err := client.Query(ctx, "support-docs", "how long do refunds take?", &moss.QueryOptions{
		TopK: 3,
	})
	if err != nil {
		log.Fatal(err)
	}

	for _, doc := range search.Docs {
		fmt.Printf("%s %.3f\n", doc.ID, doc.Score)
	}
}
```

## Custom embeddings

If your documents already have embeddings, omit `ModelID` and the SDK will
default to `"custom"` automatically:

```go
docs := []moss.DocumentInfo{
	{
		ID:        "doc-1",
		Text:      "Attach a caller-provided embedding.",
		Embedding: []float32{1, 0, 0, 0},
	},
	{
		ID:        "doc-2",
		Text:      "This index uses custom vectors.",
		Embedding: []float32{0, 1, 0, 0},
	},
}

_, err := client.CreateIndex(ctx, "custom-embeddings", docs, nil)
if err != nil {
	log.Fatal(err)
}

results, err := client.Query(ctx, "custom-embeddings", "", &moss.QueryOptions{
	Embedding: []float32{1, 0, 0, 0},
	TopK:      5,
})
```

All documents must either provide embeddings or omit them entirely in the same
batch.

## Examples

Runnable examples live here:

- [`examples/basic/main.go`](./examples/basic/main.go)
- [`examples/custom-embeddings/main.go`](./examples/custom-embeddings/main.go)

## Integration tests

Live tests are skipped unless both of these are set:

```bash
export MOSS_TEST_PROJECT_ID=...
export MOSS_TEST_PROJECT_KEY=...
```

Then run:

```bash
cd sdks/go/sdk
go test ./...
```

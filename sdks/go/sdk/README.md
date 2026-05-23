# Moss client library for Go

`moss` provides a typed Go client for Moss semantic search workflows.

The Go SDK now has two layers:

- a public SDK in `sdks/go/sdk`
- native `libmoss` bindings in `sdks/go/bindings`

## Features

- typed Go client and models
- bindings-backed index creation and document mutation
- bindings-backed index metadata and document reads
- local index loading and query via native bindings
- optional caller-provided embeddings for custom indexes
- env-gated live integration tests

## Current limitations

- the SDK requires the `libmoss` C SDK and the `libmoss` build tag for real runtime operations
- `LoadIndexOptions.CachePath` is not exposed by the current `libmoss` C API yet

## Installation

From this repository, use the module at:

```go
github.com/usemoss/moss/sdks/go/sdk/moss
```

Download the `libmoss` C SDK release and build with `-tags libmoss`. The
bindings setup is documented in
[`../bindings/README.md`](../bindings/README.md).

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
	defer client.Close()

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

	if _, err := client.LoadIndex(ctx, "support-docs", &moss.LoadIndexOptions{}); err != nil {
		log.Fatal(err)
	}

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

if _, err := client.LoadIndex(ctx, "custom-embeddings", &moss.LoadIndexOptions{}); err != nil {
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

Run them with native bindings enabled:

```bash
export CGO_CFLAGS="-I<libmoss-sdk-root>/include"
export CGO_LDFLAGS="-L<libmoss-sdk-root>/lib"
export LD_LIBRARY_PATH="<libmoss-sdk-root>/lib"
go run -tags libmoss ./examples/basic
```

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
CGO_CFLAGS="-I<libmoss-sdk-root>/include" \
CGO_LDFLAGS="-L<libmoss-sdk-root>/lib" \
LD_LIBRARY_PATH="<libmoss-sdk-root>/lib" \
go test -tags libmoss ./...
```

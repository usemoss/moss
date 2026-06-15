# Moss Go Examples

Runnable examples for the Moss Go SDK.

## Examples

- [`basic/main.go`](./basic/main.go) creates an index, loads it, queries it, and deletes it.
- [`custom-embeddings/main.go`](./custom-embeddings/main.go) uses caller-provided vectors for documents and queries.

## Run

Set your Moss credentials:

```bash
export MOSS_PROJECT_ID=...
export MOSS_PROJECT_KEY=...
```

Runtime operations require the `libmoss` C SDK and the `libmoss` build tag:

```bash
export CGO_CFLAGS="-I<libmoss-sdk-root>/include"
export CGO_LDFLAGS="-L<libmoss-sdk-root>/lib"
export LD_LIBRARY_PATH="<libmoss-sdk-root>/lib"

go run -tags libmoss ./basic
go run -tags libmoss ./custom-embeddings
```

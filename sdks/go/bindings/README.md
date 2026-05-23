# Moss Go Bindings

This package wraps the native `libmoss` runtime for Go via CGO.

It mirrors the role of the other language bindings packages in this repository:

- native runtime access
- local index loading
- local query execution
- cloud-backed manage operations exposed through the native client

## Status

The real bindings implementation is compiled only with the `libmoss` build tag.
Without that tag, this package builds a stub that returns a clear
`ErrBindingsUnavailable` error.

## Local build workflow

Download the matching `libmoss` C SDK release archive for your platform from:

- <https://github.com/usemoss/moss/releases/tag/c-sdk-v0.9.0>

For Linux `x86_64`, extract the archive somewhere local so you have:

```text
<sdk-root>/
├── include/libmoss.h
└── lib/libmoss.so
```

Then build with:

```bash
export CGO_CFLAGS="-I<sdk-root>/include"
export CGO_LDFLAGS="-L<sdk-root>/lib"
export LD_LIBRARY_PATH="<sdk-root>/lib"
go test -tags libmoss ./...
```

The Go SDK module can then be built with the same flags and tag.

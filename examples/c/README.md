# Moss C SDK Examples

This project demonstrates the usage of the Moss C SDK (`libmoss`) for semantic search and document indexing.

## Setup

From this directory (`examples/c`), download the `libmoss` archive for your platform from the [`c-sdk-v0.9.0` release](https://github.com/usemoss/moss/releases/tag/c-sdk-v0.9.0) and extract it so that `include/` and `lib/` sit alongside the `.c` files.

| Archive | OS | Arch |
| --- | --- | --- |
| `libmoss-v0.9.0-aarch64-apple-darwin.tar.gz` | macOS | ARM64 (Apple Silicon) |
| `libmoss-v0.9.0-x86_64-unknown-linux-gnu.tar.gz` | Linux | x86_64 |
| `libmoss-v0.9.0-aarch64-unknown-linux-gnu.tar.gz` | Linux | ARM64 |
| `libmoss-v0.9.0-x86_64-pc-windows-msvc.tar.gz` | Windows | x86_64 |

For example, on Apple Silicon macOS:

```bash
gh release download c-sdk-v0.9.0 --repo usemoss/moss \
  --pattern 'libmoss-v0.9.0-aarch64-apple-darwin.tar.gz'
tar xzf libmoss-v0.9.0-aarch64-apple-darwin.tar.gz --strip-components=1
```

After extraction, this directory should contain:

```
examples/c/
├── README.md
├── example_usage.c
├── metadata_filtering.c
├── session_usage.c
├── include/
│   └── libmoss.h
└── lib/
    ├── libmoss.dylib  (or .so / .dll)
    └── libmoss.a      (or .lib)
```

## Running Samples

Each sample reads `MOSS_PROJECT_ID` and `MOSS_PROJECT_KEY` from the environment. You can also pass them as positional arguments (`./<sample> <id> <key>`), but env vars are preferred so the key doesn't end up in shell history or `ps` output.

```bash
export MOSS_PROJECT_ID=...
export MOSS_PROJECT_KEY=...
```

### macOS

Build and run any sample (replace `<sample>` with `session_usage`, `example_usage`, or `metadata_filtering`):

```bash
clang <sample>.c -o <sample> \
  -Iinclude -Llib -lmoss \
  -framework Security -framework SystemConfiguration

DYLD_LIBRARY_PATH=lib ./<sample>
```

`DYLD_LIBRARY_PATH=lib` is required at runtime: the prebuilt `libmoss.dylib` has a build-server install path baked in, and this env var redirects the dynamic loader to your local copy.

### Linux

```bash
gcc <sample>.c -o <sample> \
  -Iinclude -Llib -lmoss \
  -lpthread -lm -ldl

LD_LIBRARY_PATH=lib ./<sample>
```

## What each sample does

- **`session_usage.c`**: Create a client, open a session, add documents with metadata, query (with and without filters), then push the session to the cloud.
- **`example_usage.c`**: Full cloud CRUD: create an index, list/get indexes, add and delete documents, run semantic search, clean up.
- **`metadata_filtering.c`**: Create an index, load it locally, and run queries filtered with `$eq`, `$and`, `$in`, and `$near` operators.

## Requirements

- C compiler (`clang` on macOS, `gcc` on Linux)
- Valid Moss project credentials. Get them at [moss.dev](https://moss.dev).

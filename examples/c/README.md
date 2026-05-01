# Moss C SDK Examples

This project demonstrates the usage of the Moss C SDK (`libmoss`) for semantic search and document indexing.

## Setup

Download `libmoss` for your platform from the [latest release](https://github.com/usemoss/moss/releases) and extract it next to these examples:

| Archive | OS | Arch |
| --- | --- | --- |
| `libmoss-vX.Y.Z-aarch64-apple-darwin.tar.gz` | macOS | ARM64 (Apple Silicon) |
| `libmoss-vX.Y.Z-x86_64-unknown-linux-gnu.tar.gz` | Linux | x86_64 |
| `libmoss-vX.Y.Z-aarch64-unknown-linux-gnu.tar.gz` | Linux | ARM64 |
| `libmoss-vX.Y.Z-x86_64-pc-windows-msvc.tar.gz` | Windows | x86_64 |

Each archive contains an `include/` directory (with `libmoss.h`) and a `lib/` directory (with `libmoss.{dylib,so,dll}` and `libmoss.{a,lib}`). The build commands below assume these sit in the current directory — if you extracted elsewhere, replace `include` and `lib` with the appropriate paths.

## Running Samples

Each sample takes your Moss project credentials as CLI arguments:

```bash
./<sample> <project_id> <project_key>
```

### Session Usage

Create a client, open a session, add documents with metadata, query, and push to the cloud:

```bash
clang session_usage.c -o session_usage \
  -Iinclude -Llib -lmoss \
  -framework Security -framework SystemConfiguration

export DYLD_LIBRARY_PATH=lib
./session_usage <project_id> <project_key>
```

### Comprehensive Cloud Example

Full cloud CRUD workflow — create index, add/get/delete docs, query, cleanup:

```bash
clang example_usage.c -o example_usage \
  -Iinclude -Llib -lmoss \
  -framework Security -framework SystemConfiguration

./example_usage <project_id> <project_key>
```

### Metadata Filtering Sample

Create an index, load it locally, and run queries filtered by document metadata using `$eq`, `$and`, `$in`, and `$near` operators:

```bash
clang metadata_filtering.c -o metadata_filtering \
  -Iinclude -Llib -lmoss \
  -framework Security -framework SystemConfiguration

./metadata_filtering <project_id> <project_key>
```

## Linux

Replace the `clang` invocation with `gcc` and swap the framework flags:

```bash
gcc <sample>.c -o <sample> \
  -Iinclude -Llib -lmoss \
  -lpthread -lm -ldl

export LD_LIBRARY_PATH=lib
./<sample> <project_id> <project_key>
```

## Requirements

- C compiler (`clang` on macOS, `gcc` on Linux)
- Valid Moss project credentials

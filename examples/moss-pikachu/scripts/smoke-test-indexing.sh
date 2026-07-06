#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Missing .env with MOSS_PROJECT_ID and MOSS_PROJECT_KEY"
  exit 1
fi

set -a
source .env
set +a

SCOPE_DIR="${TMPDIR:-/tmp}/moss-pikachu-smoke"
mkdir -p "$SCOPE_DIR"
SESSION_NAME="moss-pikachu-smoke"

TEST_FILE="$SCOPE_DIR/moss-pikachu-smoke-test.md"
BINARYISH_FILE="$SCOPE_DIR/moss-pikachu-smoke-artifact.weirdbin"
UNIQUE="smoke-$(date +%s)"
echo "Moss Pikachu smoke test unique phrase: $UNIQUE" > "$TEST_FILE"
printf '\001\002\003metadata-fallback-%s\004' "$UNIQUE" > "$BINARYISH_FILE"

WORKER="$ROOT/MossPikachu/Resources/moss_worker.py"
PYTHON="$ROOT/.venv/bin/python3"
[[ -x "$PYTHON" ]] || PYTHON=python3

CACHE_DIR="${TMPDIR:-/tmp}/moss-pikachu-smoke-cache"
mkdir -p "$CACHE_DIR"

OUTPUT=$(
  {
    printf '%s\n' "{\"action\":\"init_session\",\"index_name\":\"$SESSION_NAME\",\"cache_path\":\"$CACHE_DIR\"}"
    printf '%s\n' "{\"action\":\"add_docs\",\"files\":[\"$TEST_FILE\",\"$BINARYISH_FILE\"]}"
    printf '%s\n' "{\"action\":\"query\",\"query\":\"$UNIQUE\",\"top_k\":3}"
    printf '%s\n' "{\"action\":\"query\",\"query\":\"weirdbin artifact\",\"top_k\":3}"
    printf '%s\n' "{\"action\":\"save_session\",\"cache_path\":\"$CACHE_DIR\"}"
  } | "$PYTHON" "$WORKER" 2>&1
)

echo "$OUTPUT"

echo "$OUTPUT" | grep -q '"status": "ok"' || { echo "init/add failed"; exit 1; }
echo "$OUTPUT" | grep -q '"chunks_indexed"' || { echo "add_docs missing chunks"; exit 1; }
echo "$OUTPUT" | grep -q "$UNIQUE" || { echo "query did not return test content"; exit 1; }
echo "$OUTPUT" | grep -q "moss-pikachu-smoke-artifact.weirdbin" || { echo "metadata fallback did not index unknown file type"; exit 1; }
echo "$OUTPUT" | grep -q "$SESSION_NAME" || { echo "expected smoke session"; exit 1; }
echo "$OUTPUT" | grep -q '"doc_count"' || { echo "save_session did not return doc_count"; exit 1; }

echo "SMOKE TEST PASSED"

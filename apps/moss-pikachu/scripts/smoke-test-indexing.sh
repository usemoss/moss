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

SCOPE_DIR="$HOME/Downloads/cwp-stuff"
mkdir -p "$SCOPE_DIR"

TEST_FILE="$SCOPE_DIR/moss-pikachu-smoke-test.md"
UNIQUE="smoke-$(date +%s)"
echo "Moss Pikachu smoke test unique phrase: $UNIQUE" > "$TEST_FILE"

WORKER="$ROOT/MossPikachu/Resources/moss_worker.py"
PYTHON="$ROOT/.venv/bin/python3"
[[ -x "$PYTHON" ]] || PYTHON=python3

OUTPUT=$(
  {
    printf '%s\n' '{"action":"init_session","index_name":"cwp-stuff"}'
    printf '%s\n' "{\"action\":\"add_docs\",\"files\":[\"$TEST_FILE\"]}"
    printf '%s\n' "{\"action\":\"query\",\"query\":\"$UNIQUE\",\"top_k\":3}"
  } | "$PYTHON" "$WORKER" 2>&1
)

echo "$OUTPUT"

echo "$OUTPUT" | grep -q '"status": "ok"' || { echo "init/add failed"; exit 1; }
echo "$OUTPUT" | grep -q '"chunks_indexed"' || { echo "add_docs missing chunks"; exit 1; }
echo "$OUTPUT" | grep -q "$UNIQUE" || { echo "query did not return test content"; exit 1; }
echo "$OUTPUT" | grep -q "cwp-stuff" || { echo "result path outside cwp-stuff scope"; exit 1; }

echo "SMOKE TEST PASSED"

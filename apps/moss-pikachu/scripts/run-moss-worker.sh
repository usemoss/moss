#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKER="${MOSS_WORKER_PATH:-$ROOT/MossPikachu/Resources/moss_worker.py}"

if [[ -x "$ROOT/.venv/bin/python3" ]]; then
  exec "$ROOT/.venv/bin/python3" "$WORKER"
fi

exec python3 "$WORKER"

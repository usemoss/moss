#!/usr/bin/env bash
# Picklight CLI bootstrap: Python venv + optional credential check.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "Picklight bootstrap"
echo "==================="

"${ROOT}/scripts/setup-moss-venv.sh"

if ! "${ROOT}/.venv/bin/python3" -c "from moss import MossClient" 2>/dev/null; then
  echo "Error: Moss Python package is not importable after venv setup." >&2
  exit 1
fi

if [[ -f .env ]]; then
  echo "Found .env in project root."
elif [[ -n "${MOSS_PROJECT_ID:-}" && -n "${MOSS_PROJECT_KEY:-}" ]]; then
  echo "Found MOSS_PROJECT_ID / MOSS_PROJECT_KEY in environment."
else
  echo ""
  echo "Moss credentials not found in .env or environment."
  echo "  Option A: cp .env.example .env and add MOSS_PROJECT_ID / MOSS_PROJECT_KEY"
  echo "  Option B: enter credentials in the Picklight setup window on first launch (⌘R)"
fi

if [[ "${1:-}" == "--smoke" ]]; then
  echo ""
  echo "Running smoke test..."
  "${ROOT}/scripts/smoke-test-indexing.sh"
fi

echo ""
echo "Ready. Open MossPikachu.xcodeproj and press ⌘R, or run:"
echo "  ./scripts/run-moss-worker.sh"

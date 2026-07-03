#!/usr/bin/env bash
set -euo pipefail
PHASE="${1:-1}"
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"

case "$PHASE" in
  1)
    xcodebuild -project MossPikachu.xcodeproj -scheme MossPikachu -destination 'platform=macOS' build
    echo "Phase 1: build OK — run in Xcode and verify menu bar + ⌘⇧M overlay"
    ;;
  2)
    test -f .venv/bin/python3 || { echo "Run ./scripts/setup-moss-venv.sh first"; exit 1; }
    .venv/bin/python3 -c "from moss import MossClient; print('moss import OK')"
    xcodebuild -project MossPikachu.xcodeproj -scheme MossPikachu -destination 'platform=macOS' build
    echo "Phase 2: Moss SDK + build OK"
    ;;
  3)
    xcodebuild -project MossPikachu.xcodeproj -scheme MossPikachu -destination 'platform=macOS' build
    echo "Phase 3: build OK — run end-to-end search test manually"
    ;;
  *)
    echo "Usage: validate-phase.sh [1|2|3]"
    exit 1
    ;;
esac

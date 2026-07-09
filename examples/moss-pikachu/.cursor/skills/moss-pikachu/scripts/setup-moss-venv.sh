#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install "moss>=1.6.0"
echo "Moss venv ready at $ROOT/.venv"

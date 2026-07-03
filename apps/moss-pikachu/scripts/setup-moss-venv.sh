#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install "moss>=1.6.0" pypdf python-docx beautifulsoup4 pillow

# Convert sticker to PNG for NSImage if source webp exists
if [[ -f capvolt-sticker.webp ]]; then
  python3 -c "
from PIL import Image
img = Image.open('capvolt-sticker.webp').convert('RGBA')
img.save('MossPikachu/Resources/capvolt-sticker.png')
print('Sticker PNG ready')
"
fi

echo "Moss venv ready at $ROOT/.venv"

#!/usr/bin/env bash
# Drop this example into a TEN Framework checkout (README Quick start, step 2).
#
# Usage: ./setup.sh /path/to/ten-framework
#
# Reuses the sibling voice-assistant example's harness (Taskfile, scripts,
# Dockerfile), swaps in this tenapp/, and seeds ai_agents/.env from this
# directory's .env if present.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
TEN_ROOT=${1:?usage: ./setup.sh /path/to/ten-framework}
EXAMPLES="$TEN_ROOT/ai_agents/agents/examples"
TARGET="$EXAMPLES/voice-assistant-with-moss"

if [[ ! -d "$EXAMPLES/voice-assistant" ]]; then
  echo "error: $TEN_ROOT does not look like a TEN Framework checkout" >&2
  echo "       (missing ai_agents/agents/examples/voice-assistant)" >&2
  exit 1
fi

if [[ -e "$TARGET" ]]; then
  echo "error: $TARGET already exists; remove it to re-run setup" >&2
  exit 1
fi

cp -R "$EXAMPLES/voice-assistant" "$TARGET"
rm -rf "$TARGET/tenapp"
cp -R "$HERE/tenapp" "$TARGET/tenapp"
chmod +x "$TARGET"/tenapp/scripts/*.sh

ENV_FILE="$TEN_ROOT/ai_agents/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  cp "$TEN_ROOT/ai_agents/.env.example" "$ENV_FILE"
fi
if [[ -f "$HERE/.env" ]]; then
  {
    echo
    echo "# --- appended by apps/ten-moss/setup.sh ---"
    cat "$HERE/.env"
  } >>"$ENV_FILE"
  echo "Appended $HERE/.env to $ENV_FILE"
else
  echo "note: no $HERE/.env found; fill in $ENV_FILE by hand"
fi

cat <<EOF

Done. Example installed at:
  $TARGET

Next, from that directory (inside TEN's dev container, or with TEN tooling
installed locally):
  task install && task run

Then open http://localhost:3000 and select the voice_assistant graph.
EOF

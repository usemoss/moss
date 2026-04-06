#!/usr/bin/env bash
# Install Moss Search skill for Zo Computer.
#
# Usage:
#   bash install.sh <project_id> <project_key>
#
# Or via curl one-liner (for Zo terminal):
#   curl -fsSL https://raw.githubusercontent.com/usemoss/moss/main/packages/zo-computer/zo-skill/install.sh | bash -s -- <project_id> <project_key>
set -euo pipefail

SKILL_DIR="/home/workspace/Skills/moss-search"
MOSS_ENV="$HOME/.config/moss/zo.env"
MCPORTER_CONFIG="$HOME/.mcporter/mcporter.json"
REPO_URL="https://raw.githubusercontent.com/usemoss/moss/main/packages/zo-computer/zo-skill"

# --- Args ---
if [ $# -lt 2 ]; then
  echo "Usage: install.sh <MOSS_PROJECT_ID> <MOSS_PROJECT_KEY>"
  echo ""
  echo "Get your credentials at https://moss.dev"
  exit 1
fi

PROJECT_ID="$1"
PROJECT_KEY="$2"

echo "Installing Moss Search skill for Zo..."

# --- Check dependencies ---
for cmd in node jq; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "Error: $cmd is required but not installed."
    exit 1
  fi
done

# --- Download skill files ---
echo "Downloading skill files..."
mkdir -p "$SKILL_DIR/scripts"

curl -fsSL "$REPO_URL/SKILL.md" -o "$SKILL_DIR/SKILL.md"
curl -fsSL "$REPO_URL/scripts/moss.sh" -o "$SKILL_DIR/scripts/moss.sh"
chmod +x "$SKILL_DIR/scripts/moss.sh"

# --- Store credentials ---
echo "Saving credentials..."
mkdir -p "$(dirname "$MOSS_ENV")"
printf 'MOSS_PROJECT_ID=%q\nMOSS_PROJECT_KEY=%q\n' \
  "$PROJECT_ID" "$PROJECT_KEY" > "$MOSS_ENV"
chmod 600 "$MOSS_ENV"

# --- Configure MCPorter ---
echo "Configuring MCPorter..."
mkdir -p "$(dirname "$MCPORTER_CONFIG")"

MOSS_SERVER='{"command": "npx", "args": ["-y", "@moss-tools/mcp-server"]}'

if [ -f "$MCPORTER_CONFIG" ]; then
  # Merge into existing config (write to temp file to avoid truncating on jq failure)
  EXISTING=$(cat "$MCPORTER_CONFIG")
  echo "$EXISTING" | jq --argjson srv "$MOSS_SERVER" --arg id "$PROJECT_ID" --arg key "$PROJECT_KEY" \
    '.mcpServers.moss = ($srv + {env: {MOSS_PROJECT_ID: $id, MOSS_PROJECT_KEY: $key}})' \
    > "${MCPORTER_CONFIG}.tmp" && mv "${MCPORTER_CONFIG}.tmp" "$MCPORTER_CONFIG"
else
  # Create new config
  jq -n --argjson srv "$MOSS_SERVER" --arg id "$PROJECT_ID" --arg key "$PROJECT_KEY" \
    '{mcpServers: {moss: ($srv + {env: {MOSS_PROJECT_ID: $id, MOSS_PROJECT_KEY: $key}})}}' \
    > "$MCPORTER_CONFIG"
fi
chmod 600 "$MCPORTER_CONFIG"

# --- Verify ---
echo ""
echo "Verifying connection..."
if bash "$SKILL_DIR/scripts/moss.sh" list-indexes 2>/dev/null; then
  echo ""
  echo "Moss Search installed successfully!"
else
  echo ""
  echo "Skill files installed. Connection test failed — verify your credentials."
  echo "You can test manually: bash $SKILL_DIR/scripts/moss.sh list-indexes"
fi

echo ""
echo "Files:"
echo "  Skill:   $SKILL_DIR/"
echo "  Creds:   $MOSS_ENV"
echo "  MCPorter: $MCPORTER_CONFIG"
echo ""
echo "Try it: bash $SKILL_DIR/scripts/moss.sh search <index-name> \"your query\""

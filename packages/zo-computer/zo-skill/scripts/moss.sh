#!/usr/bin/env bash
# Moss semantic search CLI for Zo — wraps @moss-tools/mcp-server via MCPorter.
#
# Usage:
#   moss.sh load-index <index>
#   moss.sh search <index> <query> [top_k]
#   moss.sh create-index <index> <docs-json>
#   moss.sh list-indexes
#   moss.sh add-docs <index> <docs-json>
#   moss.sh delete-docs <index> <doc-ids-json>
#   moss.sh get-docs <index> [doc-ids-json]
#   moss.sh delete-index <index>
set -euo pipefail

MCPORTER_VERSION="0.7.3"
MCPORTER_CONFIG="$HOME/.mcporter/mcporter.json"
MOSS_ENV="$HOME/.config/moss/zo.env"

if [ -f "$MOSS_ENV" ]; then
  source "$MOSS_ENV"
fi

usage() {
  echo "Usage: moss.sh <command> [args]"
  echo ""
  echo "Commands:"
  echo "  load-index <index>                  Preload index into memory for sub-10ms queries"
  echo "  search <index> <query> [top_k]      Semantic search"
  echo "  create-index <index> <docs-json>    Create index with documents"
  echo "  list-indexes                        List all indexes"
  echo "  add-docs <index> <docs-json>        Add documents"
  echo "  delete-docs <index> <ids-json>      Delete documents by ID"
  echo "  get-docs <index> [ids-json]         Retrieve documents"
  echo "  delete-index <index>                Delete an index"
  exit 1
}

mcp() {
  npx -y "mcporter@${MCPORTER_VERSION}" --config "$MCPORTER_CONFIG" call "moss.$1" "${@:2}" 2>&1
}

if [ $# -lt 1 ]; then
  usage
fi

COMMAND="$1"
shift

case "$COMMAND" in
  load-index)
    [ $# -lt 1 ] && { echo "Usage: moss.sh load-index <index>"; exit 1; }
    mcp load_index indexName:"$1"
    ;;
  search)
    [ $# -lt 2 ] && { echo "Usage: moss.sh search <index> <query> [top_k]"; exit 1; }
    INDEX="$1"; QUERY="$2"; TOP_K="${3:-5}"
    mcp query indexName:"$INDEX" query:"$QUERY" topK:"$TOP_K"
    ;;
  create-index)
    [ $# -lt 2 ] && { echo "Usage: moss.sh create-index <index> <docs-json>"; exit 1; }
    mcp create_index indexName:"$1" docs:"$2"
    ;;
  list-indexes)
    mcp list_indexes
    ;;
  add-docs)
    [ $# -lt 2 ] && { echo "Usage: moss.sh add-docs <index> <docs-json>"; exit 1; }
    mcp add_docs indexName:"$1" docs:"$2"
    ;;
  delete-docs)
    [ $# -lt 2 ] && { echo "Usage: moss.sh delete-docs <index> <doc-ids-json>"; exit 1; }
    mcp delete_docs indexName:"$1" docIds:"$2"
    ;;
  get-docs)
    [ $# -lt 1 ] && { echo "Usage: moss.sh get-docs <index> [doc-ids-json]"; exit 1; }
    if [ $# -ge 2 ]; then
      mcp get_docs indexName:"$1" docIds:"$2"
    else
      mcp get_docs indexName:"$1"
    fi
    ;;
  delete-index)
    [ $# -lt 1 ] && { echo "Usage: moss.sh delete-index <index>"; exit 1; }
    mcp delete_index indexName:"$1"
    ;;
  *)
    echo "Unknown command: $COMMAND"
    usage
    ;;
esac

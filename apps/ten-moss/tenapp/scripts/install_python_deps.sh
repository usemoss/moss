#!/usr/bin/env bash

# Fail loudly: abort on any error, unset var, or failed pipe — so a failed
# dependency install (e.g. ten-moss) fails `task install` immediately instead of
# surfacing later as an import error at startup. (Patch on the vendored baseline.)
set -euo pipefail

# Set default pip install command
PIP_INSTALL_CMD=${PIP_INSTALL_CMD:-"uv pip install --system"}

install_python_requirements() {
  local app_dir=$1

  echo "Starting Python dependencies installation..."


  # Install Twilio server Python dependencies
  if [[ -f "$app_dir/../server/requirements.txt" ]]; then
    echo "Installing Twilio server Python dependencies..."
    ${PIP_INSTALL_CMD} -r "$app_dir/../server/requirements.txt"
  else
    echo "No requirements.txt found in server directory: $app_dir/../server"
  fi

  # Traverse ten_packages/extension directory to find requirements.txt
  if [[ -d "$app_dir/ten_packages/extension" ]]; then
    echo "Traversing ten_packages/extension directory..."
    for extension in "$app_dir/ten_packages/extension"/*; do
      if [[ -d "$extension" && -f "$extension/requirements.txt" ]]; then
        echo "Found requirements.txt in $extension, installing dependencies..."
        ${PIP_INSTALL_CMD} -r "$extension/requirements.txt"
      fi
    done
  else
    echo "ten_packages/extension directory not found"
  fi

  # Traverse ten_packages/system directory to find requirements.txt
  if [[ -d "$app_dir/ten_packages/system" ]]; then
    echo "Traversing ten_packages/system directory..."
    for extension in "$app_dir/ten_packages/system"/*; do
      if [[ -d "$extension" && -f "$extension/requirements.txt" ]]; then
        echo "Found requirements.txt in $extension, installing dependencies..."
        ${PIP_INSTALL_CMD} -r "$extension/requirements.txt"
      fi
    done
  else
    echo "ten_packages/system directory not found"
  fi

  echo "Python dependencies installation completed!"
}

warm_moss_model_cache() {
  # Download the Moss embedding model once, before any worker starts. Two
  # workers starting at the same moment on a cold cache race the download and
  # corrupt it; grounding then fails best-effort and the agent runs ungrounded.
  # (Patch on the vendored baseline.)
  if [[ -z "${MOSS_PROJECT_ID:-}" || -z "${MOSS_PROJECT_KEY:-}" || -z "${MOSS_INDEX_NAME:-}" ]]; then
    echo "MOSS_* env vars not set; skipping Moss model warmup"
    return 0
  fi
  echo "Warming the Moss embedding model cache..."
  python3 - <<'PY' || echo "WARNING: Moss model warmup failed; the first session will download the model"
import asyncio
import os

from ten_moss import MossSessionManager


async def main() -> None:
    manager = MossSessionManager(
        project_id=os.environ["MOSS_PROJECT_ID"],
        project_key=os.environ["MOSS_PROJECT_KEY"],
        index_name=os.environ["MOSS_INDEX_NAME"],
        model_id="moss-minilm",
    )
    await manager.open()
    print(f"Moss model cache warm (doc_count={manager.doc_count})")


try:
    asyncio.run(main())
except Exception as exc:  # noqa: BLE001 - warmup is best-effort
    # Never fail `task install` over the warmup: a cold cache, unreachable
    # index endpoint, etc. just mean the first session downloads the model.
    # Print one clean line instead of dumping a traceback.
    print(f"WARNING: Moss model warmup skipped ({exc}); first session will download the model")
PY
}

build_go_app() {
  local app_dir=$1
  cd $app_dir

  go run "$app_dir/ten_packages/system/ten_runtime_go/tools/build/main.go" --verbose
  if [[ $? -ne 0 ]]; then
    echo "FATAL: failed to build go app, see logs for detail."
    exit 1
  fi
}

main() {
  # Get the parent directory of script location as app root directory
  APP_HOME=$(
    cd $(dirname $0)/..
    pwd
  )

  echo "App root directory: $APP_HOME"
  echo "Using pip command: $PIP_INSTALL_CMD"

  # Check if manifest.json exists
  if [[ ! -f "$APP_HOME/manifest.json" ]]; then
    echo "Error: manifest.json file not found"
    exit 1
  fi

  build_go_app "$APP_HOME"

  # Install Python dependencies
  install_python_requirements "$APP_HOME"

  warm_moss_model_cache
}

# If script is executed directly, run main function
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi

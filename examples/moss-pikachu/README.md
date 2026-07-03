# Moss Pikachu

Native macOS menu bar app for semantic file search powered by [Moss](https://github.com/usemoss/moss).

- **Hotkey:** ⌘⇧M to open search
- **Pet:** Pikachu animates on search results
- **Privacy:** Queries run locally via Moss Python SDK session

## Prerequisites

- macOS 12+
- Xcode 15+
- Python 3.10+

## Setup

1. **Moss credentials** — Sign up at [moss.dev](https://moss.dev) and copy your project ID and key.

2. **Python environment:**
   ```bash
   ./scripts/setup-moss-venv.sh
   ```

3. **Configure credentials** (choose one):
   ```bash
   export MOSS_PROJECT_ID=your_id
   export MOSS_PROJECT_KEY=your_key
   ```
   Or create `.env` in the project root (loaded automatically in dev builds):
   ```bash
   cp .env.example .env
   ```
   Xcode can also use **Scheme → Run → Environment Variables**.

4. **Sticker asset**: place `capvolt-sticker.webp` at project root; setup script generates `MossPikachu/Resources/capvolt-sticker.png`.

5. **Open in Xcode:**
   ```bash
   open MossPikachu.xcodeproj
   ```
   Build and run (⌘R).

## Development

```bash
# Phase validation
chmod +x scripts/*.sh
./scripts/smoke-test-indexing.sh
./.cursor/skills/moss-pikachu/scripts/validate-phase.sh 1

# Debug logging
# Run with --debug argument in Xcode scheme → logs to ~/Library/Application Support/MossPikachu/moss-pikachu.log
```

## Architecture

- **Swift app** — Menu bar UI, FSEvents file monitor, search overlay
- **moss_worker.py** — Python subprocess using `pip install moss>=1.6.0` SessionIndex API
- **Index manifest** — Swift tracks indexed files across launches (Python session is in-memory)

See [`.cursor/skills/moss-pikachu/`](.cursor/skills/moss-pikachu/) for agent development guidance.

## Vendor

Optional reference clone of the Moss OSS repo:
```bash
git submodule add https://github.com/usemoss/moss vendor/moss
```

The app uses the **PyPI** `moss` package (not editable install from GitHub main SDK).

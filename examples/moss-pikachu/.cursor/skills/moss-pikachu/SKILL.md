---
name: moss-pikachu
description: >-
  Build and maintain Moss Pikachu, a macOS menu bar semantic file search app
  using Moss Python SDK (PyPI moss>=1.6.0), FSEvents, SwiftUI, and Pikachu pet
  animations. Use when working on MossPikachu, moss_worker.py, FileMonitor,
  SearchService, menu bar overlay, or Moss integration in this repository.
---

# Moss Pikachu Agent Skill

## Project docs (start here)

| Doc | Purpose |
|-----|---------|
| [project-summary.md](../../project-summary.md) | Full technical reference |
| [how-to.md](../../../how-to.md) | End-user guide |
| [contribution.md](../../contribution.md) | Contributor guide |

## Specialized skills

| Skill | Use when |
|-------|----------|
| [moss-pikachu-semantic-search](../moss-pikachu-semantic-search/SKILL.md) | Search quality, query tuning |
| [moss-pikachu-indexing](../moss-pikachu-indexing/SKILL.md) | Indexing, manual/automatic modes |
| [moss-pikachu-contributing](../moss-pikachu-contributing/SKILL.md) | PRs and contribution workflow |

## Read order

1. [architecture.md](architecture.md)
2. [moss-integration.md](moss-integration.md)
3. [macos-patterns.md](macos-patterns.md)
4. [ui-animations.md](ui-animations.md)
5. [pitfalls.md](pitfalls.md)

## Non-negotiables

- **Xcode `.app` bundle** — not a root-level SPM executable for the menu bar app
- **macOS-only target** — `SUPPORTED_PLATFORMS = macosx`
- **Python worker** for Moss on macOS — Moss Swift SPM is iOS-only
- **`pip install moss>=1.6.0`** — GitHub `main` `sdks/python/sdk` lacks `SessionIndex` API
- **No hardcoded credentials** — `MOSS_PROJECT_ID` / `MOSS_PROJECT_KEY` via Keychain or env
- **NSPanel** for search overlay — not `WindowGroup` (avoids Dock icon)

## Phase gates

Run before advancing phases:

```bash
./.cursor/skills/moss-pikachu/scripts/validate-phase.sh 1
./.cursor/skills/moss-pikachu/scripts/validate-phase.sh 2
./.cursor/skills/moss-pikachu/scripts/validate-phase.sh 3
```

## Task sequencing

| Phase | Scope |
|-------|-------|
| 1 | Menu bar, hotkey, search overlay shell, settings window |
| 2 | FileMonitor, moss_worker.py, MossBridge, SearchService |
| 3 | Pikachu animations, live search UI, settings, polish |

Do not wire live search before MossBridge + SearchService compile and pass Phase 2 validation.

## Code conventions

- `@MainActor` for all UI updates
- `async/await` for MossBridge calls (not callbacks)
- Line-delimited JSON between Swift and Python (`\n` terminated)
- Debounce FSEvents (100ms) and search input (200ms)
- `MARK:` sections in Swift service files

# Architecture

## Component map

```
AppDelegate
├── NSStatusBar (menu: Search, Settings, Quit)
├── HotKeyManager (⌘⇧M)
├── SearchOverlayController (NSPanel)
└── SettingsWindowController

SearchOverlayView
├── PikachuPetView
├── ResultsListView
└── SearchService (injected)

SearchService
├── FileMonitor (FSEvents)
├── IndexManager (file manifest in Application Support)
└── MossBridge → moss_worker.py subprocess
```

## Data flow

1. **Launch:** SearchService.initialize() → start MossBridge → init_session → scan folders → add_docs
2. **File change:** FileMonitor → debounce → SearchService.indexFiles → MossBridge.addDocs
3. **Search:** SearchOverlayView → debounced query → SearchService.search → MossBridge.query → results
4. **Quit:** FileMonitor.stop → MossBridge.saveSession (push_index if cloud sync) → terminate worker

## File ownership

| Path | Owner |
|------|-------|
| `MossPikachu/AppDelegate.swift` | Menu bar lifecycle |
| `MossPikachu/Views/SearchOverlayController.swift` | NSPanel window chrome |
| `MossPikachu/Services/MossBridge.swift` | Subprocess JSON protocol |
| `MossPikachu/Resources/moss_worker.py` | Moss SessionIndex loop |
| `~/Library/Application Support/MossPikachu/` | Index manifest, logs |

## Persistence (no Python disk API)

Python `SessionIndex` has no `save_to_disk` / `load_from_disk`. Persistence strategy:

- **In-session:** worker holds SessionIndex in memory while app runs
- **Across launches:** Swift `IndexManager` stores `{path, mtime}` manifest; rescan only changed files
- **Optional cloud:** `push_index()` when user enables Moss cloud sync in Settings

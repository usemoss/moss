# Picklight — How To Use

A plain-language guide for using Picklight in your daily workflow. No coding required.

---

## What Picklight does

Picklight is a small **desktop pet** that lets you **search your files by meaning**, not just by exact filename. Ask things like:

- "quarterly budget spreadsheet"
- "lease agreement 2024"
- "resume pdf"
- "notes from standup about auth"

**How it works:** On launch, Picklight loads your Moss API key and restores a **local search index** from this Mac (`~/Library/Application Support/Picklight/moss-session-cache`). Search runs as soon as Moss is ready. In the background, it indexes your enabled folders — by default **Documents, Desktop, and Downloads** — and saves progress every 500 files and when you quit. Your file contents are **not uploaded** to Moss cloud; the API key is used only to run Moss semantic search locally in memory.

---

## First-time setup

### 1. Get Moss credentials

1. Sign up at [moss.dev](https://moss.dev)
2. Create a project and copy your **Project ID** and **Project Key**

### 2. Build and run

```bash
open MossPikachu.xcodeproj
```

Press **⌘R**. Xcode automatically sets up the Python environment on first build.

### 3. Add your credentials

On first launch, Picklight shows a **setup window** — enter your Project ID and Project Key and click **Save & Continue**.

Alternatively, choose one of these before launching:

**Option A — `.env` file (easiest for dev builds)**

```bash
cp .env.example .env
# Edit .env and paste your MOSS_PROJECT_ID and MOSS_PROJECT_KEY
```

**Option B — Environment variables**

```bash
export MOSS_PROJECT_ID=your_id
export MOSS_PROJECT_KEY=your_key
```

**Option C — Settings later**

Right-click the pet → **Settings** → **Update credentials**

### 4. Grant folder access

If macOS asks for permission to access Desktop, Documents, or Downloads, click **Allow**. You can fix denied folders later in **System Settings → Privacy & Security → Files and Folders**.

---

## Daily use

### Open search

| Method | How |
|--------|-----|
| **Hotkey** | Press **⌘⇧M** (Command + Shift + M) |
| **Click pet** | Left-click the floating pet |
| **Context menu** | Right-click pet → **Search** |

### Search

1. A **cloud thought bubble** appears near the pet
2. Type what you're looking for in plain language
3. Results appear below the input (up to 4 visible)
4. **Click** a result or use **arrow keys + Enter** to open the file
5. Press **Escape** or click outside to close

### Move the pet

- **Drag** the pet anywhere on screen
- Release with momentum — it slides smoothly to a stop
- Position is remembered between launches

### Settings

Right-click the pet → **Settings**

---

## Settings explained

### Setup

- **Moss credentials** — configured or missing; use **Update credentials** to change
- **Python + Moss** — whether the local Python environment is ready
- **Retry Initialize** — re-run setup if Python or Moss failed to load
- Folder permission warnings appear here if a folder could not be accessed

### Indexed Folders

Default on: **Documents**, **Desktop**, **Downloads**.

Optional (off by default): Movies, Music, Pictures, Public, iCloud Drive.

Click **Save** after changing folders to trigger a rescan if scope changed.

### Index Status

Shows how many files and chunks are indexed, plus buttons:

- **Index Now** — update the index with current files
- **Clear & Rescan** — full reset (use if results seem corrupted)

### Search style

| Option | Best for |
|--------|----------|
| **Keyword-heavy** | Finding files by exact words in filename or content |
| **Balanced** | Everyday mixed searches (recommended) |
| **Semantic** | Conceptual queries ("that paper about transformers") |

After changing search style, just search — no re-index needed.

### About

Shows version and whether **Pet assets** (Capvolt spritesheet) loaded correctly.

---

## Tips for better search results

1. **Be specific** — "invoice acme march 2024" beats "invoice"
2. **Try keyword-heavy mode** when you know part of the filename
3. **Try semantic mode** when you remember the topic but not the name
4. **Run Index Now** if you recently added many files or switched machines
5. **Check for "Missing" badges** — result is in your Moss session but file moved/deleted on disk

---

## What gets indexed

### Full content extracted

`.md`, `.txt`, `.rtf`, `.html`, `.pdf` (first 40 pages), `.docx`

### Searchable by metadata only

All other file types (images, videos, zip files, etc.) are indexed by:

- Filename
- Full path
- Folder name
- Extension
- File size

### Never indexed

Folders inside: `.git`, `node_modules`, `.venv`, caches, logs, app containers, and hidden files.

---

## Privacy

- **Search queries run locally** in memory via the Moss Python worker
- Your files are read locally for indexing
- Moss session data is cached on disk under `~/Library/Application Support/Picklight/`
- No queries are sent to the cloud per search — only session storage/sync uses your API keys

---

## Troubleshooting

### Pet appears but search says "Moss session is still opening…"

Wait a few seconds. Large Moss sessions take time to load into memory. If it persists, open **Settings** and click **Retry Initialize**.

### "Moss credentials missing"

Use the first-run setup window, **Settings → Update credentials**, or set `.env` / environment variables.

### Python or Moss not installed

Run `./scripts/setup-moss-venv.sh` or rebuild in Xcode (⌘R). Check **Settings → Python + Moss** for the error message.

### Cannot access Documents / Desktop / Downloads

Grant access in **System Settings → Privacy & Security → Files and Folders**, then click **Retry Initialize** in Settings.

### No results for something you know exists

1. Check **Settings → Session docs** — is the count > 0?
2. Run **Index Now** if the file was never indexed
3. Try **Keyword-heavy** search style
4. File may be outside enabled folders

### Results show "Missing"

The file was in your Moss index but no longer exists at that path (moved, renamed, or deleted).

### Debug logging

Run with `--debug` in Xcode scheme arguments. Logs write to:

```
~/Library/Application Support/Picklight/picklight.log
```

---

## Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| `⌘⇧M` | Toggle search overlay |
| `↑` / `↓` | Navigate results |
| `Enter` | Open selected result |
| `Escape` | Close search overlay |

---

## Quitting

Right-click the pet → **Quit Picklight**

On quit, Picklight saves any unsaved index changes to your local Moss session cache.

---

## Quick reference

| I want to… | Do this |
|------------|---------|
| Search my files | `⌘⇧M`, type query |
| Update my index | Settings → Index Now |
| Start fresh | Settings → Clear & Rescan |
| Add more folders | Settings → Indexed Folders → Save |
| Fix bad Moss keys | Settings → Update credentials |
| Fix Python/Moss errors | Settings → Retry Initialize |
| Change search sensitivity | Settings → Search style |
| Move the pet | Drag it |
| Open settings | Right-click pet → Settings |

---

*For technical architecture details, see [project-summary.md](project-summary.md). For contributing, see [contribution.md](contribution.md).*

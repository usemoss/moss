# Moss JavaScript SDK Examples

Runnable TypeScript examples for `@moss-dev/moss` v1.3.1.

## Setup

```bash
# 1. Install dependencies
npm install

# 2. Create your .env file
cp .env.template .env
# Fill in MOSS_PROJECT_ID, MOSS_PROJECT_KEY, and MOSS_INDEX_NAME
```

## Samples at a glance

| Script | npm command | Needs existing index? | Extra env var |
| --- | --- | --- | --- |
| `load_and_query_sample.ts` | `npm run load-and-query` | Yes (`MOSS_INDEX_NAME`) | — |
| `cached_load_sample.ts` | `npm run cached-load` | Yes (`MOSS_INDEX_NAME`) | — |
| `custom_authenticator_sample.ts` | `npm run custom-auth` | Yes (`MOSS_INDEX_NAME`) | — |
| `session_sample.ts` | `npm run session` | No (creates session in-memory) | — |
| `session_cache_sample.ts` | `npm run session-cache` | No | — |
| `session_custom_auth_sample.ts` | `npm run session-custom-auth` | No | — |
| `comprehensive_sample.ts` | `npm run comprehensive` | No (creates + deletes its own) | — |
| `custom_embedding_sample.ts` | `npm run custom-embedding` | No (creates + deletes its own) | `OPENAI_API_KEY` |

---

## Sample-by-sample testing guide

### 1. `load_and_query_sample.ts`

Loads an existing index and runs three queries against it.

**Requires:** An index that already exists in your project.

```bash
MOSS_INDEX_NAME=my-existing-index npm run load-and-query
```

**What to verify:**

- `Index loaded successfully` appears
- Each query prints results with `score` values

---

### 2. `cached_load_sample.ts`

Shows disk caching and auto-refresh. Run it twice to see the speed difference.

**Requires:** An existing index.

```bash
MOSS_INDEX_NAME=my-existing-index npm run cached-load
```

**What to verify:**

- First run: downloads from cloud, creates `.moss-cache/` directory
- Second run: loads in `<10ms` from disk
- The auto-refresh section loads without error and prints a confirmation

---

### 3. `custom_authenticator_sample.ts`

Starts an in-process token server (your "backend") and queries via a client that holds no project key.

**Requires:** An existing index.

```bash
MOSS_INDEX_NAME=my-existing-index npm run custom-auth
```

**What to verify:**

- `Token server listening on http://localhost:3456/moss-token`
- `Index loaded successfully` using the authenticator client
- Query results print without error
- `Token server stopped.` at the end

---

### 4. `session_sample.ts`

Creates a local `SessionIndex`, adds documents in-memory, queries it (~1-10ms), then pushes to the cloud.

**No existing index required.** Set `MOSS_INDEX_NAME` to any name for the session.

```bash
MOSS_INDEX_NAME=my-session npm run session
```

**What to verify:**

- `Session open` shows `0 existing docs` (first run) or prior doc count (resumed)
- Query returns results ranked by score
- `Pushed N docs` confirms cloud sync

---

### 5. `session_cache_sample.ts`

Saves a session to disk with `saveToDisk`, then restores it into a fresh session without touching the cloud.

**No existing index required.**

```bash
npm run session-cache
```

**What to verify:**

- `.moss-session-cache/` directory is created
- `Fresh session docs before restore: 0`
- `Restored 3 docs from disk` after `loadFromDisk`
- Query against the restored session returns results
- Device ID file path printed at the end

---

### 6. `session_custom_auth_sample.ts`

Opens a session using a custom `IAuthenticator` (token-based, no project key in the client).

**No existing index required.**

```bash
npm run session-custom-auth
```

**What to verify:**

- `Session open` via the authenticator
- Docs added and query returns results
- `documents stayed on the device` message at the end

---

### 7. `comprehensive_sample.ts`

End-to-end tour of the full API: creates a temporary index, exercises every major method, then deletes it.

**No existing index required.** Uses a timestamped name so it never collides with real data.

```bash
npm run comprehensive
```

**What to verify:**

- Steps 1–14 complete without errors
- Step 9 (metadata filter) returns only `technology` category docs
- Step 13 (SessionIndex) shows in-memory add + query + push
- Step 14 prints `Index deleted: true`

---

### 8. `custom_embedding_sample.ts`

Creates an index with OpenAI embeddings, adds more docs, queries via cloud fallback then locally.

**Requires:** `OPENAI_API_KEY` in addition to Moss credentials.
**No existing Moss index required.** Uses `MOSS_INDEX_NAME` as the name to create and delete.

```bash
MOSS_INDEX_NAME=custom-emb-test npm run custom-embedding
```

**What to verify:**

- Embedding dimensions printed (`1536` for `text-embedding-3-small`)
- Cloud query and local query both return results
- `Index deleted.` in the cleanup block

---

## Troubleshooting

| Error | Fix |
| --- | --- |
| `Cannot find module '@moss-dev/moss'` | Run `npm install` |
| `Missing environment variables` | Copy `.env.template` → `.env` and fill in values |
| `index does not exist` | Create one first via `npm run comprehensive`, or use the Moss dashboard |
| `Auth failed HTTP 401` | Check `MOSS_PROJECT_ID` and `MOSS_PROJECT_KEY` are correct |
| OpenAI errors in custom-embedding | Verify `OPENAI_API_KEY` is set and has credits |

## Requirements

- Node.js 20+
- `@moss-dev/moss` 1.3.1 (installed via `npm install`)

# Deep Moss ↔ TEN Framework Integration — Design

**Date:** 2026-07-14
**Status:** Approved; in implementation
**Author:** Harsha Nalluru (with Claude)

> **Revision 2026-07-15 (supersedes stale sections below):** During review the
> reusable component was reframed from a "retrieval store" to a **Moss session
> manager**, built on the Moss [Sessions API](https://docs.moss.dev/docs/reference/python/sessions).
> The class is `MossSessionManager` (config `MossSessionConfig`). Its surface
> mirrors the SDK — `open()`, `add_docs()`, `get_docs()`, `delete_docs()`,
> `push_index()`, `doc_count` — plus one convenience, `query_context(text) -> str`,
> for injection-ready grounding (the raw query is not exposed). Name mapping:
> `MossRetrievalStore`→`MossSessionManager`, `load()`→`open()`, `retrieve()`→`query_context()`.
>
> This supersedes two body sections below:
> - **"No write-back / memorization"** — no longer a non-goal. Sessions are
>   read+write, so the manager exposes `add_docs()`/`push_index()` (still not
>   used by the v1 demo flow, but available).
> - **Testing** — the unit tests are fully **offline** and mock the Moss client
>   (`packages/ten-moss/tests/test_session_manager.py`); they do **not** create a
>   live index or need `MOSS_PROJECT_ID`/`MOSS_PROJECT_KEY`.

## Summary

Build a deep integration between [Moss](https://moss.dev) (sub-10ms on-device semantic
search runtime for conversational AI) and the [TEN Framework](https://github.com/ten-framework/ten-framework)
(open-source framework for real-time multimodal conversational AI).

The integration ships two deliverables:

1. **`packages/ten-moss/`** — a reusable Python helper package exposing a
   `MossRetrievalStore` that any TEN extension can use for retrieval.
2. **`apps/ten-moss/`** — a runnable TEN voice-assistant example
   (`voice-assistant-with-moss`) that wires Moss in as an ambient RAG layer.

The pattern is modeled 1:1 on TEN Agent's own RAG/memory integrations
(`voice-assistant-with-memU`, `voice-assistant-with-PowerMem`,
`voice-assistant-with-EverMemOS`).

## Goals

- A voice agent that, on **every final ASR transcript**, queries a Moss index
  (hybrid semantic + keyword, <10ms) and injects the retrieved knowledge into
  the LLM prompt **before** the model answers — grounding responses with no
  perceptible added latency.
- A reusable, offline-testable helper package (`ten-moss`) that others can drop
  into any TEN extension.
- A complete, documented, runnable example that demonstrates the value.

## Non-Goals (YAGNI)

- **No write-back / memorization.** v1 queries a pre-built knowledge index only.
  (A create-index helper is provided; upserting conversation turns is a later
  feature.)
- **No standalone graph-node extension.** Retrieval is baked into the control
  extension, matching TEN's proven RAG pattern; a separate `moss_retrieval_python`
  graph node fights the main-control-centric flagship graph.
- **Python only.** No Go/TypeScript ports.
- **Ambient only.** No LLM-tool / `cmd`-invoked retrieval mode.

## Decisions (locked)

| Decision | Choice |
| --- | --- |
| Deliverable | Reusable package **+** runnable example app |
| Language | Python |
| Retrieval mode | Ambient / always-on (on each final ASR turn) |
| Package shape | Helper package + Moss-wired `main_python` control extension |
| Example location | `apps/ten-moss/` |
| Write-back | Read-only RAG v1 + create-index helper |
| Default TTS in example | ElevenLabs (swappable — one node in `property.json`) |

## Upstream reference (pinned)

The example vendors a trimmed copy of TEN's control extension. Reference:

- Repo: `ten-framework/ten-framework`
- Commit: `c385d2724a1f3e6ac4ee0b81fcc7dada8346c0e0` (2026-07-14)
- Path: `ai_agents/agents/examples/voice-assistant-with-memU/`

Keeping the Moss-specific delta minimal (see "The `main_python` delta") limits
drift risk from this upstream.

## Architecture

### Runtime data flow

```
mic ─▶ agora_rtc ─▶ streamid_adapter ─▶ stt(deepgram) ─┐
                                                        │ data: asr_result (final)
                                                        ▼
                                              main_control (main_python)
                                                 │  MossRetrievalStore.retrieve(text)
                                                 ▼  ── Moss hybrid query <10ms ──▶ index
                                                 │  ◀── top-k docs ──
                              queue_llm_input("{context}\n\n[Current User Question]\n{text}")
                                                 ▼
                                       llm(openai) ─▶ sentences ─▶ tts ─▶ agora_rtc ─▶ speaker
```

Transcripts flow to `message_collector2` → `agora_rtc` data channel → frontend.
Topology matches the memU example minus the memorization path and memory tool.

### Component 1 — `packages/ten-moss/` (reusable helper)

Layout mirrors `packages/pipecat-moss/`:

```
packages/ten-moss/
  pyproject.toml
  README.md
  CHANGELOG.md
  CONTRIBUTING.md
  LICENSE
  .env.example
  .gitignore
  src/ten_moss/
    __init__.py                 # exports MossRetrievalStore, MossRetrievalConfig
    moss_retrieval_store.py     # MossRetrievalStore
    config.py                   # MossRetrievalConfig (pydantic mixin)
  examples/
    create_index.py             # build + populate a demo index (generic)
  tests/
    test_retrieval_store.py     # offline: create → load → query → assert
```

**`MossRetrievalStore`** (the Moss analog of TEN's `MemoryStore`):

```python
class MossRetrievalStore:
    def __init__(
        self,
        *,
        project_id: str,
        project_key: str,
        index_name: str,
        top_k: int = 5,
        alpha: float = 0.8,          # 1.0 = pure semantic, 0.0 = pure keyword
        context_header: str = "Relevant knowledge from Moss:",
        logger=None,                 # optional; falls back to loguru/no-op
        timeout_s: float = 2.0,      # guard so a network hiccup can't stall a turn
    ): ...

    async def load(self) -> None:
        """Load the index once at startup. Raises on failure (fail fast)."""

    async def retrieve(self, query: str) -> str:
        """Hybrid query; returns a formatted context block, or '' on no hits/error."""

    def format_context(self, docs) -> str:
        """Build '{header}\n[1] ...\n[2] ...' from Moss result docs."""
```

- `load()` → `client.load_index(index_name)`; failure raises.
- `retrieve()` → `client.query(index_name, query, QueryOptions(top_k=..., alpha=...))`,
  wrapped in `asyncio.wait_for(..., timeout_s)`; any exception, timeout, or zero
  results → log + return `""` (never breaks the voice loop).
- `format_context()` → numbered passages under the configurable header.

**`MossRetrievalConfig`** — a pydantic mixin so property names are standardized
across consumers: `moss_project_id`, `moss_project_key`, `moss_index_name`,
`moss_top_k`, `moss_alpha`, `moss_context_header`, `enable_moss`.

### Component 2 — `apps/ten-moss/` (runnable TEN voice app)

Modeled on `voice-assistant-with-memU`:

```
apps/ten-moss/
  README.md
  .env.example
  data/
    knowledge.jsonl             # sample corpus for the demo index
  tenapp/
    manifest.json               # TEN app deps (via tman)
    property.json               # the graph (nodes + connections)
    ten_packages/extension/main_python/
      extension.py              # vendored control extension + Moss delta
      addon.py
      config.py                 # + Moss fields
      agent/ ...                # vendored orchestration helpers
      helper.py
      manifest.json
      property.json
```

**Graph nodes** (`property.json → predefined_graphs[0].graph.nodes`):
`agora_rtc` (transport/RTC), `streamid_adapter`, `stt` (`deepgram_asr_python`),
`main_control` (`main_python`), `llm` (`openai_llm2_python`), `tts`
(`elevenlabs_tts2_python`), `message_collector` (`message_collector2`).

**Connections:** `stt` → `main_control` (`data: asr_result`); RTC audio in →
`streamid_adapter` → `stt`; `tts` audio → `agora_rtc`; `message_collector` →
`agora_rtc` data. Same shape as the memU example, minus the weather tool /
memorization.

### The `main_python` delta (kept minimal to limit drift)

Only three touch points vs. the stock control extension:

1. **`config.py`** — add the `MossRetrievalConfig` fields.
2. **`on_init`** — construct `MossRetrievalStore` from config and `await store.load()`
   (skip entirely if `enable_moss` is false).
3. **`_on_asr_result`** (final, non-empty only):
   ```python
   ctx = await self.moss_store.retrieve(event.text)
   if ctx:
       await self.agent.queue_llm_input(
           f"{ctx}\n\n[Current User Question]\n{event.text}"
       )
   else:
       await self.agent.queue_llm_input(event.text)
   ```

No memorization path (read-only v1).

## Configuration surface

On the `main_control` node in `property.json` (env-substituted):

| Property | Example | Notes |
| --- | --- | --- |
| `moss_project_id` | `${env:MOSS_PROJECT_ID}` | Moss project id |
| `moss_project_key` | `${env:MOSS_PROJECT_KEY}` | Moss project key |
| `moss_index_name` | `${env:MOSS_INDEX_NAME}` | index to load/query |
| `moss_top_k` | `5` | results per query |
| `moss_alpha` | `0.8` | semantic/keyword blend |
| `moss_context_header` | `"Relevant knowledge from Moss:"` | header of injected block |
| `enable_moss` | `true` | master toggle |

`.env.example` (app): `MOSS_PROJECT_ID`, `MOSS_PROJECT_KEY`, `MOSS_INDEX_NAME`,
`AGORA_APP_ID`, `AGORA_APP_CERTIFICATE`, `DEEPGRAM_API_KEY`, `OPENAI_API_KEY`,
`OPENAI_MODEL`, `ELEVENLABS_TTS_KEY`.

## Error handling (voice must never stall)

- **Startup:** `store.load()` failure → log + raise (fail fast on a misconfigured
  index). Entire Moss path skipped when `enable_moss=false`.
- **Per-turn:** any exception, timeout (`asyncio.wait_for`), or zero hits →
  return `""`, log, and the LLM still receives the raw question.
- Retrieval only fires on **final, non-empty** transcripts.

## Testing

- **CI-able** — `packages/ten-moss/tests/test_retrieval_store.py`: create an
  ephemeral index, add docs, `load()`, `retrieve()`; assert top-k count, score
  ordering, context-block format, and graceful empty/error → `""`. Uses
  `MOSS_PROJECT_ID`/`MOSS_PROJECT_KEY` like other Moss integration tests; skips
  if creds absent.
- **Manual E2E** — full app via `task run`; talk to it and confirm answers
  reflect indexed knowledge. **Not** CI-runnable (needs the TEN toolchain/Docker
  + Agora + Deepgram/OpenAI/ElevenLabs keys). Documented in the app README.

## Delivery plan — 3 PRs

The example app is split so the bulky vendored copy and the Moss integration
land separately, making the actual integration a small, focused review.

**PR 1 — `packages/ten-moss/` (reusable core).** `MossRetrievalStore`,
`MossRetrievalConfig`, `examples/create_index.py`, offline tests, packaging
files, package README. **This design spec commits here.** Adds the package to
`AGENTS.md` + root README. Self-contained and CI-green.

**PR 2 — `apps/ten-moss/` baseline.** A faithful, working TEN voice assistant
(vendored `main_python`, graph, transport/STT/LLM/TTS wiring) with **no Moss
yet**. Isolates the upstream copy. Independently reviewable as a clean baseline.

**PR 3 — Moss wiring.** The 3-point delta (`config.py` fields, `on_init` load,
`_on_asr_result` inject), `moss_*` properties in `property.json`, `ten-moss` as a
path/editable dependency, `data/knowledge.jsonl` sample corpus + create-index
step, `MOSS_*` in `.env.example`, and README/AGENTS.md/integrations-table docs.
The small, interesting diff.

**Dependencies:** PR 3 stacks on PR 2 and needs PR 1 merged. PR 1 and PR 2 are
independent off `main`.

**Optional PR 4 (follow-up):** publish `ten-moss` to PyPI + release notes once
both stabilize.

## Risks

1. **Vendored-copy drift.** The example copies TEN's control extension. Mitigated
   by keeping the Moss delta to the three points above and pinning the upstream
   reference (see above).
2. **E2E not CI-runnable.** External toolchain + paid keys. Covered by offline
   unit tests + documented manual steps.
3. **In-container index loading.** Moss loads an index using its bundled
   embedding model inside the TEN container; note runtime/download expectations
   in the app README.

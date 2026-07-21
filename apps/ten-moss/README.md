# Voice Assistant with Moss (TEN Framework)

A real-time voice agent built on the [TEN Framework](https://github.com/ten-framework/ten-framework) that grounds its answers in a [Moss](https://moss.dev) session. On every final ASR transcript the control extension queries Moss for session-scoped context and prepends it to the LLM prompt before the model responds. That retrieval runs in-process (single-digit milliseconds, no network round-trip), so grounding adds no perceptible latency to the turn.

The Moss integration lives in the `main_python` control extension and is powered by the [`ten-moss`](https://pypi.org/project/ten-moss/) package (`MossSessionManager`).

## How it works

```
caller speaks
  │
  ▼
agora_rtc                  real-time audio transport (in / out)
  │
  ▼
streamid_adapter           routes audio (PCM) frames to STT
  │
  ▼
stt · deepgram             speech → text
  │  asr_result (final)
  ▼
main_control · main_python
  │  1. query_context(text)  ──▶  Moss session   (in-process index)
  │  2. grounding            ◀──                  (<10 ms, no network hop)
  │  3. queue_llm_input(grounding + user question)
  ▼
llm · openai               generates the reply
  │
  ▼
tts · elevenlabs           text → speech
  │
  ▼
agora_rtc   ──▶   caller hears the answer
```

The Moss delta over the stock TEN voice assistant is small and lives in three places in `main_python`:

- `config.py`: `MainControlConfig` inherits `MossSessionConfig` (the `moss_*` properties).
- `extension.py` `on_init`: opens the Moss session (`MossSessionManager.from_config(...).open()`), best-effort.
- `extension.py` `_on_asr_result`: `query_context(text)` and prepends the grounding to the user's turn.

## Provenance

The `tenapp/` baseline (graph, `main_python` control extension, agent runtime, scripts) is vendored from the TEN Framework `voice-assistant` example at commit
[`c385d27`](https://github.com/ten-framework/ten-framework/tree/c385d2724a1f3e6ac4ee0b81fcc7dada8346c0e0/ai_agents/agents/examples/voice-assistant),
licensed under **Apache-2.0** (headers preserved). Only the Moss delta described above is Moss-authored.

Two small correctness patches were applied on top of the vendored baseline:
`agent/decorators.py` fixes the `agent_event_handler` annotation to `type[AgentEvent]`,
and `extension.py` parses `session_id` defensively so a non-numeric value can't crash the
ASR handler.

## Prerequisites

- A **TEN Framework checkout**. This example references shared TEN extensions via relative paths (`../../../ten_packages/extension/...`) and runs with TEN's own tooling, so it lives **inside** a TEN Framework repo. It ships the TEN app (`tenapp/`), not the repo-level run harness (playground / server / Taskfile / Dockerfile), which the TEN Framework provides.
- A **Moss** project (`MOSS_PROJECT_ID` / `MOSS_PROJECT_KEY`), [moss.dev](https://moss.dev).
- Provider keys: **Agora** (transport), **Deepgram** (STT), **OpenAI** (LLM), **ElevenLabs** (TTS).

## Run

1. **Build the demo knowledge index** (from this directory, needs only the Moss SDK):
   ```bash
   cp .env.example .env      # fill in MOSS_PROJECT_ID / MOSS_PROJECT_KEY / MOSS_INDEX_NAME
   python create_index.py    # reads data/knowledge.jsonl, creates MOSS_INDEX_NAME
   ```

2. **Drop the app into a TEN checkout.** Create an example dir at
   `ten-framework/ai_agents/agents/examples/voice-assistant-with-moss/` by copying the sibling
   `voice-assistant` example (for its `Taskfile.yml`, `scripts/`, and `Dockerfile` run harness),
   then replace that copy's `tenapp/` with this repo's `tenapp/`. `main_python` depends on
   [`ten-moss`](https://pypi.org/project/ten-moss/) (listed in `main_python/requirements.txt`),
   so `task install` installs it from PyPI automatically.

3. **Run with TEN's tooling** from that example dir (`task install && task run`, per the TEN
   docs), with the `MOSS_*` vars from step 1 plus the provider keys from Prerequisites
   (Agora / Deepgram / OpenAI / ElevenLabs). Open the TEN playground (http://localhost:3000),
   select the **`voice_assistant`** graph (or open `?graph=voice_assistant`), and ask something
   covered by `data/knowledge.jsonl`, e.g. *"how long do refunds take?"*, to hear grounded answers.

## Per-turn latency and retrieval logs (live, in the agent)

Every turn, the control extension logs the retrieval cost using the SDK's own
`SearchResult.time_taken_ms` (surfaced by `ten-moss` as `last_time_taken_ms`), with the
wall-clock alongside for reference:

```
[retrieval-latency] backend=moss(in-process) time_taken_ms=2 (wall_clock=64ms)
```

And in the playground transcript you see, per turn, **what Moss retrieved + the SDK
`time_taken_ms`**, followed by the **LLM's answer**:

```
🔎 Moss · retrieved in 2 ms (SDK time_taken_ms)
   Relevant knowledge from Moss: [1] Refunds are processed within 3-5 business days…
<the assistant's spoken answer>
```

It also emits a **per-turn latency breakdown**: a grep-able log line *and* a note in the
transcript, so you can see where the turn's time goes across the pipeline:

```
[latency-breakdown] turn=3 moss_retrieval_ms=2 llm_ttft_ms=480 llm_total_ms=1150 turn_total_ms=1160
```

- **moss_retrieval_ms**: the SDK's `SearchResult.time_taken_ms` (in-process retrieval engine time).
- **llm_ttft_ms**: time to the LLM's first token after dispatch.
- **llm_total_ms**: full LLM generation for the turn.
- **turn_total_ms**: ASR-final → LLM-final (the whole control-side turn).

ASR timing appears in the Deepgram STT extension logs and TTS audio-out in the ElevenLabs
TTS logs (both per turn in the worker log), so between those and the line above you get the
full component-by-component breakdown.

**Hear the latency Moss saves.** Set `moss_simulate_remote_ms` on the `main_control`
node in `tenapp/property.json` to imitate a remote store's network round trip, then
re-run `task run`:

- `0`   → Moss in-process (~2 ms), the agent replies immediately.
- `400` → the same agent, same answer, but audibly **pauses ~400 ms before every reply**.

## Configuration

Moss is configured on the `main_control` node in `tenapp/property.json`, values
env-substituted from `.env`:

| Property | Meaning |
| --- | --- |
| `moss_project_id` / `moss_project_key` | Moss credentials |
| `moss_index_name` | session index to open (create-or-resume) |
| `moss_model_id` | embedding model; empty adopts the stored index's model |
| `moss_top_k` | results per query (this app: `3`) |
| `moss_alpha` | semantic/keyword blend (`1.0` = pure semantic, `0.0` = pure keyword) |
| `moss_context_header` | header line prepended to the injected grounding |
| `enable_moss` | master toggle; `false` runs the plain assistant with no grounding |
| `moss_simulate_remote_ms` | imitate a remote store's round-trip (perf illustration) |

## Testing status

The `ten-moss` package is covered by offline unit tests (`packages/ten-moss/tests/`).
This end-to-end app is **not** run in CI, it requires the TEN toolchain plus paid
Agora/Deepgram/OpenAI/ElevenLabs credentials, so it is validated manually via the
steps above.

# Voice Assistant with Moss (TEN Framework)

A real-time voice agent built on the [TEN Framework](https://github.com/ten-framework/ten-framework) that grounds its answers in a [Moss](https://moss.dev) session. On every final ASR transcript the control extension asks Moss for session-scoped context (~1–10ms, in-process) and injects it into the LLM prompt before the model responds — so answers reflect your knowledge base with no perceptible added latency.

The Moss integration lives in the `main_python` control extension and is powered by the [`ten-moss`](../../packages/ten-moss) package (`MossSessionManager`).

## How it works

```
mic ─▶ agora_rtc ─▶ streamid_adapter ─▶ stt (deepgram) ─┐
                                                         │ data: asr_result (final)
                                                         ▼
                                               main_control (main_python)
                                                  │  MossSessionManager.context_for(text)
                                                  ▼  ── Moss session query <10ms ──▶ index
                                                  │  ◀── grounding ──
                       queue_llm_input("{context}\n\n[Current User Question]\n{text}")
                                                  ▼
                                        llm (openai) ─▶ tts (elevenlabs) ─▶ agora_rtc ─▶ speaker
```

The Moss delta over the stock TEN voice assistant is small and lives in three places in `main_python`:

- `config.py` — `MainControlConfig` inherits `MossSessionConfig` (the `moss_*` properties).
- `extension.py` `on_init` — opens the Moss session (`MossSessionManager.from_config(...).start()`), best-effort.
- `extension.py` `_on_asr_result` — `context_for(text)` and prepends the grounding to the user's turn.

## Provenance

The `tenapp/` baseline (graph, `main_python` control extension, agent runtime, scripts) is vendored from the TEN Framework `voice-assistant` example at commit
[`c385d27`](https://github.com/ten-framework/ten-framework/tree/c385d2724a1f3e6ac4ee0b81fcc7dada8346c0e0/ai_agents/agents/examples/voice-assistant),
licensed under **Apache-2.0** (headers preserved). Only the Moss delta described above is Moss-authored.

## Prerequisites

- The **TEN Framework toolchain** (`tman` + the TEN dev image / Docker). This example references shared TEN extensions via relative paths (`../../../ten_packages/extension/...`), so it is designed to run **inside a TEN Framework checkout** — copy `tenapp/` into `ten-framework/ai_agents/agents/examples/voice-assistant-with-moss/`, or clone TEN and drop it in.
- A **Moss** project (`MOSS_PROJECT_ID` / `MOSS_PROJECT_KEY`) — [moss.dev](https://moss.dev).
- Provider keys: **Agora** (transport), **Deepgram** (STT), **OpenAI** (LLM), **ElevenLabs** (TTS).

## Quick start

1. **Configure environment**
   ```bash
   cp .env.example .env    # fill in Moss + provider keys
   ```

2. **Build the demo knowledge index**
   ```bash
   python create_index.py  # reads data/knowledge.jsonl, creates MOSS_INDEX_NAME
   ```

3. **Install & run** (inside the TEN environment)
   ```bash
   task install   # runs scripts/install_python_deps.sh (installs ten-moss + extensions)
   task run       # starts the agent
   ```
   - Frontend: http://localhost:3000 · API: http://localhost:8080 · TMAN Designer: http://localhost:49483

   > **Note:** until `ten-moss` is published to PyPI, install it editable so `main_python` can import it:
   > ```bash
   > uv pip install --system -e ../../packages/ten-moss
   > ```

4. **Talk to it.** Ask something covered by `data/knowledge.jsonl` (e.g. *"how long do refunds take?"*) and the answer will reflect the indexed knowledge.

## Configuration

Moss is configured on the `main_control` node in `tenapp/property.json` (env-substituted):
`moss_project_id`, `moss_project_key`, `moss_index_name`, `moss_model_id`,
`moss_top_k`, `moss_alpha`, `moss_context_header`, `enable_moss`. Set `enable_moss`
to `false` to run the plain voice assistant with no grounding.

## Testing status

The `ten-moss` package is covered by offline unit tests (`packages/ten-moss/tests/`).
This end-to-end app is **not** run in CI — it requires the TEN toolchain plus paid
Agora/Deepgram/OpenAI/ElevenLabs credentials, so it is validated manually via the
steps above.

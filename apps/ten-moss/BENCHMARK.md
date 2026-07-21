# TEN default retrieval (memU) vs Moss — per-turn latency

Same framework (TEN), same voice pipeline (Agora → Deepgram → LLM → ElevenLabs),
same questions. The only thing that changes is **where retrieval happens**:

| Agent | Retrieval backend | Where it runs |
| --- | --- | --- |
| `voice-assistant-with-memU` (TEN's shipped example) | memU | **remote** — HTTPS to `api.memu.so` every turn |
| `voice-assistant-with-moss` (this repo) | Moss | **in-process** — local session, no network hop |

memU is TEN's flagship memory example; OceanBase PowerRAG and EverMemOS (TEN's other
options) are remote services too. So this is representative of TEN's default: retrieval
is a network round trip. Moss runs where the agent runs.

Both agents log the same line each turn, so you can read the difference directly:

```
[retrieval-latency] backend=memU(cloud)     took 380 ms this turn
[retrieval-latency] backend=moss(in-process) took 2 ms this turn
```

## 1. Instrument TEN's memU example (one small edit)

In your TEN checkout, open
`ai_agents/agents/examples/voice-assistant-with-memU/tenapp/ten_packages/extension/main_python/extension.py`
and, inside `_on_asr_result`, wrap the retrieval call:

```python
# before
            related_memory = await self._retrieve_related_memory(event.text)

# after
            import time
            _t0 = time.perf_counter()
            related_memory = await self._retrieve_related_memory(event.text)
            self.ten_env.log_info(
                f"[retrieval-latency] backend=memU(cloud) took "
                f"{(time.perf_counter() - _t0) * 1000:.0f} ms this turn"
            )
```

The Moss example already logs its line (no edit needed).

## 2. Configure keys (`ai_agents/.env`)

Shared: `AGORA_APP_ID`/`AGORA_APP_CERTIFICATE`, `DEEPGRAM_API_KEY`, `OPENAI_API_KEY`,
`OPENAI_MODEL`, `ELEVENLABS_TTS_KEY`.
memU: `MEMU_API_KEY` (free trial at https://memu.pro).
Moss: `MOSS_PROJECT_ID`, `MOSS_PROJECT_KEY`, `MOSS_INDEX_NAME=ten-moss-demo`.

## 3. Run each agent and ask the same questions

```bash
docker compose up -d
docker exec -it ten_agent_dev bash

# --- Agent A: TEN default (memU) ---
task use AGENT=agents/examples/voice-assistant-with-memU
task run
# open http://localhost:3000, connect, ask: "how long do refunds take?",
# "which payment methods can I use?", "how fast is express shipping?"
# watch the logs for:  [retrieval-latency] backend=memU(cloud) took NNN ms

# --- Agent B: Moss (in a second run) ---
uv pip install --system /app/ten_moss-0.0.1-py3-none-any.whl   # once
task use AGENT=agents/examples/voice-assistant-with-moss
task run
# ask the same three questions
# watch the logs for:  [retrieval-latency] backend=moss(in-process) took N ms
```

Isolate the numbers in the terminal with:

```bash
docker logs -f ten_agent_dev 2>&1 | grep --line-buffered "[retrieval-latency]"
```

## What you'll see

- **memU (TEN default):** hundreds of ms per turn — a network round trip to `api.memu.so`
  plus server-side search, right on the hot path before the LLM can start.
- **Moss:** single-digit ms per turn (≈2 ms measured on this demo index) — the retrieval
  effectively disappears from the turn budget, so the agent starts replying immediately.

Same agent, same answer quality — Moss removes the retrieval latency that TEN's default,
remote-by-design backends add to every turn.

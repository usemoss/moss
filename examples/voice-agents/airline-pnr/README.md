# Airline Customer Voice Agent (Ambient Retrieval)

This example showcases a different retrieval pattern from the other
voice-agent examples in this folder: **ambient retrieval**.

There is no `lookup_*` tool. Every user turn automatically triggers a
Moss query against the active booking before the LLM is invoked, and
the result is injected as a system message. The LLM responds in one
shot.

```
              tool-driven retrieval                 ambient retrieval
              (mortgage, screening)                 (this example)
              ─────────────────────                 ─────────────────────
   user ─►   STT ─► LLM ─► tool decision           STT ─► [Moss query]   ┐
                              │                            │             │ in
                              ▼                            ▼             │ parallel
                          Moss query                 result injected     │
                              │                      as system msg       │
                              ▼                            │             ┘
                          tool result ─► LLM ─►  TTS       ▼
                                                          LLM ─► TTS

                          2 LLM round-trips           1 LLM round-trip
```

Why this fits airline customer service: the use case is overwhelmingly
factual Q&A. Almost every user turn needs the booking data. Tool-driven
retrieval forces the LLM to decide-to-retrieve, wait, then respond -
two round-trips per turn. With ambient retrieval the LLM responds in
one shot. The latency floor of the call drops by an LLM call per turn.

## How the three voice-agent examples differ

| Example | Retrieval pattern | When the LLM gets context |
|---|---|---|
| [`mortgage-lending/`](../mortgage-lending/) | Tool-driven, single index, multi-agent handoff | When the LLM calls `search_mortgage_kb` |
| [`candidate-screening/`](../candidate-screening/) | Tool-driven, two indexes (JD + resume) | When the LLM calls `lookup_*` |
| `airline-pnr/` (this example) | **Ambient**, per-PNR index | Always - injected as a system message before each LLM turn |

Same Moss SDK underneath; three different ways to wire it into a voice
agent.

## What this example demonstrates

| Capability | Where to look |
|---|---|
| Ambient retrieval via `on_user_turn_completed` | `agent.py` - `AirlineAgent.on_user_turn_completed` |
| Per-user (per-PNR) Moss indexes | `agent.py` - `load_booking`, `_index_name_for` |
| Mid-call index swap (companion bookings) | `agent.py` - `load_booking` invalidates verification |
| Identity verification gating ambient retrieval | `agent.py` - `verify_caller`, gated on `caller_verified` |
| Three-strikes verification + escalation | `agent.py` - `verification_attempts` |
| IVR preload via env var | `agent.py` - `INITIAL_PNR` / `BOOKING_PNR` |
| Change request capture | `agent.py` - `record_change_request`, `ChangeRequest` |
| Structured call summary as the output artifact | `agent.py` - `_build_summary`, `submit_call_summary` |
| Deterministic eval suite | `evals/test_call_summary.py` |

## The split: ambient = read, tools = write

The agent has no retrieval tool. All tools are *actions* that mutate
state or end the call:

| Tool | Purpose |
|---|---|
| `load_booking(pnr)` | Lifecycle - swap which Moss index is active |
| `verify_caller(name)` | Lifecycle - identity gate |
| `record_change_request(kind, detail)` | State capture - write to userdata |
| `add_note(note)` | State capture - write to userdata |
| `submit_call_summary()` | Terminal - emit JSON artifact |
| `escalate_to_human(reason)` | Terminal - hand off |

Reads happen ambiently. The LLM never asks Moss for booking data; it
just gets it. This is the cleanest version of the pattern.

## Privacy posture: ambient retrieval is gated

Until `verify_caller` returns success, no booking context is retrieved
or injected into the LLM's chat history. Pre-verification turns pass
through `on_user_turn_completed` untouched - the agent drives the
verification flow on its own, with only the system prompt to guide it.

Switching to a different PNR mid-call (companion booking, family
member) automatically invalidates the prior verification: the caller
must re-verify before the new booking's data starts flowing.

## Why per-user indexes

Most retrieval-augmented agents share a single large knowledge base
across all callers, then filter results by metadata (`user_id == X`).
That works for static reference content but is the wrong shape for
customer-specific data:

- Every query across a shared index has to be filtered, which limits
  retrieval quality.
- Scaling reads per user is everyone's problem, not one user's.
- A new booking shouldn't reindex the world.

A per-user index inverts this. Each booking is a tiny self-contained
index (10-15 docs). Loading one is cheap; switching between them is
cheap; querying inside one is bounded by its own size, not the
catalog total. The voice agent's retrieval cost is decoupled from the
size of the customer base.

## Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (or `pip` + `venv`)
- A [Moss](https://moss.dev) project (`MOSS_PROJECT_ID`, `MOSS_PROJECT_KEY`)
- API keys for your voice providers:
  - [OpenAI](https://platform.openai.com) - LLM
  - [Deepgram](https://deepgram.com) - speech-to-text
  - [Cartesia](https://play.cartesia.ai) - text-to-speech
- For browser-based testing only: a [LiveKit](https://livekit.io) project.
  **Not required for console mode.**

## Setup

1. **Install dependencies**

   ```bash
   uv sync
   ```

2. **Configure environment**

   ```bash
   cp .env.example .env
   ```

   Fill in your Moss credentials and provider keys.

3. **Build the booking indexes**

   ```bash
   uv run python create_indexes.py             # build all PNR fixtures
   uv run python create_indexes.py --pnr WJ7BNH  # build just one
   uv run python create_indexes.py --list        # list available fixtures
   ```

   The fixtures live in `data/`. Each file is a flat array of
   `{id, text, metadata}` documents (the canonical Moss shape) and
   the index name is derived from the filename
   (`pnr_wj7bnh.json` -> `booking-wj7bnh`).

4. **Run the agent - pick one of two modes**

   ### A) Console mode - talk in your terminal (fastest)

   ```bash
   uv run python agent.py console
   ```

   The agent grabs your mic and speakers directly. No LiveKit server,
   no browser, no frontend.

   ### B) Dev mode - connect from a browser

   ```bash
   uv run python agent.py dev
   ```

   Connect from the [LiveKit Agents Playground](https://agents-playground.livekit.io)
   or a custom React frontend.

   You can also pre-warm a specific booking via env var, the same way
   an IVR would after capturing the PNR via DTMF or speech:

   ```bash
   BOOKING_PNR=WJ7BNH uv run python agent.py dev
   ```

## Three sample bookings included

| PNR | Passenger | Itinerary | Why it's interesting |
|---|---|---|---|
| `XKQ4P2` | Meera Patel | One-way SFO -> ORD economy, no status | Simple happy path |
| `WJ7BNH` | Jide Okafor | Round trip ORD -> FRA business, Aurora Gold tier | Multi-segment, premium cabin, status benefits, international docs |
| `MR5XBP` | Aiko Tanaka (+ infant) | One-way LAX -> HNL economy plus, wheelchair, bassinet | Special service requests, infant policies |

All three are fictional. Every name, route, and price is invented.

## Try this conversation

What you would see in the agent log alongside the dialogue. Notice the
LLM never calls a retrieval tool - context just appears.

```
Agent:   Thanks for calling Aurora Air. Could I have your six-character
         booking reference, please?
Caller:  Yeah, it's WJ7BNH.

Agent:   [load_booking("WJ7BNH") -> loaded in 12ms]
         Thanks. And could you confirm the first name on the booking?
Caller:  Jide.

Agent:   [verify_caller("Jide") -> verified - ambient retrieval ON]
         Great, how can I help?
Caller:  When does my Frankfurt flight leave?

         [ambient query [WJ7BNH]: When does my Frankfurt flight leave?]
         [Moss: 4 docs in 6ms]
         [system message injected: "Booking context for WJ7BNH..."]
Agent:   Your flight AUR108 departs Chicago at 6:40 PM Central on July 5th.

Caller:  And my baggage allowance?
         [ambient query: And my baggage allowance?]
         [Moss: 4 docs in 5ms]
         [system message injected: "Booking context for WJ7BNH..."]
Agent:   You're in business, so two checked bags up to 70 pounds each
         are included, plus priority handling on your Gold tier.

Caller:  Could you switch my outbound seat? I'd prefer an aisle.
         [ambient query: Could you switch my outbound seat?]
         [Moss: 4 docs in 6ms]
Agent:   [record_change_request(kind="seat",
            detail="prefers aisle on AUR108 outbound, currently 3K")]
         I've submitted a request to move your outbound seat to an
         aisle. The crew will confirm by email before departure.

Caller:  That's all, thanks.
         [ambient query: That's all, thanks.]   <- still queries; cheap
Agent:   [submit_call_summary() -> ./call-summaries/WJ7BNH__1234.json]
         Have a good trip.
```

A small honest cost of ambient retrieval: the last "thanks" turn fires
a query that returns docs the LLM doesn't really need. At sub-10ms per
query this is fine, but it is a real difference from tool-driven where
the LLM would have skipped retrieval entirely.

## The call summary

Written to `call-summaries/<active_pnr>__<unix_ts>.json` when the
agent calls `submit_call_summary`:

```json
{
  "active_pnr": "WJ7BNH",
  "bookings_loaded": ["WJ7BNH"],
  "duration_sec": 184,
  "caller_verified": true,
  "verification_attempts": 1,
  "questions_asked": [
    "When does my Frankfurt flight leave?",
    "And my baggage allowance?",
    "Could you switch my outbound seat? I'd prefer an aisle.",
    "That's all, thanks."
  ],
  "change_requests": [
    {"kind": "seat", "detail": "prefers aisle on AUR108 outbound, currently 3K"}
  ],
  "notes": [],
  "schema_version": 1
}
```

`questions_asked` is captured automatically by the ambient retrieval
hook, not by an LLM-driven tool. That's another consequence of ambient
retrieval - some state capture moves out of the LLM's responsibilities.

## Running the eval suite

The deterministic parts of the agent (index naming, summary shape,
change-request capture) are covered by pytest:

```bash
uv run pytest evals/
```

Eight tests, no LLM or live Moss required. Treat this as the floor;
add scenario tests with real fixtures when you wire CI.

## Files

```text
airline-pnr/
├── agent.py                         # AirlineAgent + ambient hook + summary + entrypoint
├── create_indexes.py                # builds one Moss index per PNR fixture
├── data/
│   ├── pnr_xkq4p2.json              # simple one-way economy
│   ├── pnr_wj7bnh.json              # round-trip business with status
│   └── pnr_mr5xbp.json              # family + special services
├── evals/
│   └── test_call_summary.py         # deterministic summary tests
├── call-summaries/                  # runtime output (gitignored)
├── pyproject.toml
├── .env.example
├── .gitignore
└── README.md
```

## When ambient retrieval is the wrong choice

To be honest about the trade-off: ambient retrieval is great here
because the use case is mostly factual Q&A grounded in one booking.
It's a poor fit for:

- **Multi-step reasoning** that requires different queries at different
  reasoning steps (the LLM should drive that with explicit tools).
- **Many possible knowledge sources** where the right one depends on
  intent classification (a router agent makes more sense).
- **Expensive retrieval** where running a query on every turn is
  wasteful (not the case for Moss, but might matter with a remote
  vector DB at 200ms+).

The mortgage and candidate-screening examples in this folder are
intentional contrasts - they need the LLM in the driver's seat.

## Resources

- [Moss docs](https://docs.moss.dev)
- [Moss llms.txt](https://moss.dev/llms.txt)
- [LiveKit Agents docs](https://docs.livekit.io/agents/)
- [Moss GitHub](https://github.com/usemoss/moss)
- [Discord](https://moss.link/discord)

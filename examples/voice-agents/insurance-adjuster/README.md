# Insurance Claims Adjuster Voice Agent

A field voice agent for property insurance claims adjusters. Adjusters call in from the inspection site, describe damage, and get instant answers about coverage — hands-free, sub-10ms retrieval.

## What this demonstrates

| Pattern | Description |
|---------|-------------|
| **Three-index ambient retrieval** | Every adjuster utterance fires up to three `SessionIndex.query()` calls in parallel before the LLM responds — no tool call, no extra round-trip. |
| **Moss sessions for live findings** | Each logged damage item is indexed via `session.add_docs()` (local embedding, no cloud round-trip). The agent can answer "what have I logged so far?" from the findings session without a tool call. `submit_report` calls `session.push_index()` to persist the claim record to the cloud. |
| **`prewarm_fnc` parallel loading** | All four indexes load simultaneously via `asyncio.gather` at worker startup. By the time the first call arrives, every `SessionIndex` is warm — per-call entrypoint is a dict lookup, not a network call. |
| **Policy pre-selection from the frontend** | The adjuster selects a policy on the welcome screen. The policy number is embedded in the LiveKit participant token metadata and read by the agent at job start — no verbal policy exchange needed. |
| **On-device embedding** | Moss embeds locally using the bundled MiniLM model. PII never reaches an external embedding API. |
| **Web ingestion pipeline** | `ingest/crawl.py` fetches public insurance documentation (iii.org, FEMA, state DOI sites) and chunks it into Moss documents for the shared claims-kb. |

## Architecture

```
Worker starts (prewarm_fnc)
       │
       └── asyncio.gather ──────────────────────────────────────────────────┐
           moss.session("claims-kb")   moss.session("policy-fl-ho3-001")   ... (all 4 in parallel)
           All SessionIndex objects warm before the first call arrives.


Adjuster utterance (on_user_turn_completed, fires BEFORE LLM)
       │
       └── asyncio.gather ──────────────────────────────────────────────────┐
           │                              │                                  │
           ▼                              ▼                                  ▼
  kb_session.query()          policy_session.query()           claim_session.query()
  HO-3 language,              This policy's declarations,      Damage items logged
  exclusions, state rules     deductibles, endorsements        so far this call
  (always runs)               (runs once policy loaded)        (runs once first finding logged)
           │                              │                                  │
           └──────────────── all results merged ──────────────────────────┘
                                          │
                              System messages injected into chat context
                                          │
                                          ▼
                                    LLM responds (1 round-trip)
```

## Tools

The agent exposes three write tools. All reads are ambient.

| Tool | When the LLM calls it | What it does |
| ---- | --------------------- | ------------ |
| `load_policy(policy_number)` | Adjuster provides a policy number verbally | Looks up the pre-warmed `SessionIndex` for that policy; activates it for ambient retrieval; creates the per-call findings session |
| `log_finding(description, estimated_value, covered, note)` | Adjuster dictates a damage item | Appends to `SessionData.findings`; indexes the item into the live `claim_session` via `add_docs()`; publishes a `claim_update` data message to the frontend |
| `submit_report()` | Adjuster says to wrap up | Calls `claim_session.push_index()` to persist findings to the cloud; writes a local JSON report |

## Indexes

| Index | Contents | Scope |
| ----- | -------- | ----- |
| `policy-fl-ho3-001` | FL Cape Coral HO-3: $485K Coverage A, 2% hurricane deductible, water backup + ordinance endorsements | Per-policy |
| `policy-ca-ho3-002` | CA Pasadena HO-3: $620K Coverage A, 50% ordinance endorsement, scheduled jewelry/watches | Per-policy |
| `policy-tx-ho3-003` | TX Katy HO-B: $540K Coverage A, 1% wind/hail deductible, cosmetic damage exclusion | Per-policy |
| `claims-kb` | HO-3 standard policy language, coverage sections, exclusions, state guidelines (FL/CA/TX), NFIP overview, adjuster workflow | Shared — always warm |

The live `claim-{policy}-{timestamp}` session is created per call and is not pre-warmed — it starts empty and grows as the adjuster logs findings.

## Demo scenarios

### FL-HO3-001 (Florida, post-hurricane)

- "Is the pool cage covered?" → Coverage B, up to $48,500
- "What deductible applies to this wind damage?" → 2% hurricane deductible = $9,700
- "The slab cracked — is that covered?" → Not flood; check if pipe-related
- "Is mold from the water intrusion covered?" → Up to $10,000 sub-limit if from a covered peril
- "What have I logged so far?" → Agent queries the live findings session, answers without a tool call

### CA-HO3-002 (California, water damage)

- "Is the earthquake damage covered?" → No, separate CEA policy
- "What does the ordinance endorsement cover?" → 50% of Coverage A = $310,000
- "Her engagement ring was stolen — what's the limit?" → Scheduled at $18,500, no deductible
- "The flat roof leaked — covered?" → Storm damage yes; ponding/maintenance no

### TX-HO3-003 (Texas, hail)

- "What's the wind/hail deductible?" → 1% of Coverage A = $5,400
- "Hail dented the roof but didn't breach it — covered?" → Cosmetic exclusion applies
- "The insured wants to invoke appraisal" → Confirm the mandatory Texas appraisal clause process
- "Pipes burst in the winter storm — covered?" → Yes (sudden/accidental), $5,000 deductible

## Setup

### 1. Install dependencies

```bash
cd examples/voice-agents/insurance-adjuster
uv sync
```

### 2. Configure credentials

```bash
cp .env.example .env
# Fill in MOSS_PROJECT_ID, MOSS_PROJECT_KEY, LIVEKIT_*, OPENAI_API_KEY,
# DEEPGRAM_API_KEY, CARTESIA_API_KEY
```

### 3. Build indexes (one-time)

```bash
uv run python create_indexes.py
```

This creates `claims-kb`, `policy-fl-ho3-001`, `policy-ca-ho3-002`, and `policy-tx-ho3-003` in your Moss project.

**Optional — enrich the claims-kb with crawled public insurance docs:**

```bash
uv run python -m ingest.crawl --out data/crawled_kb.json
uv run python create_indexes.py --include-crawled data/crawled_kb.json
```

### 4. Run the agent

```bash
uv run python agent.py dev
```

At startup you will see all four indexes load in parallel:

```
INFO insurance-adjuster - pre-warming 4 indexes in parallel: ['claims-kb', 'policy-fl-ho3-001', ...]
INFO insurance-adjuster -   claims-kb ready
INFO insurance-adjuster -   policy-fl-ho3-001 ready
...
INFO insurance-adjuster - all indexes warm, worker ready
```

When a call comes in, entrypoint activates the pre-selected policy instantly:

```
INFO insurance-adjuster - policy FL-HO3-001 activated from pre-warmed sessions
```

**Optional:** Override the policy via env var (useful for testing without the frontend):

```bash
POLICY_NUMBER=TX-HO3-003 uv run python agent.py dev
```

### 5. Run the frontend (optional)

```bash
cd ui
cp .env.example .env.local   # fill in LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
npm install
npm run dev
```

## Project layout

```text
insurance-adjuster/
├── agent.py              # LiveKit voice agent — prewarm_fnc, ambient retrieval, Moss sessions
├── create_indexes.py     # Build per-policy + shared claims-kb indexes
├── pyproject.toml
├── .env.example
├── data/
│   ├── claims_kb.json    # Hand-authored HO-3 policy language (35 documents)
│   └── policies/
│       ├── policy_HO3_FL001.json   # Florida HO-3 (Cape Coral)
│       ├── policy_HO3_CA002.json   # California HO-3 (Pasadena)
│       └── policy_HO3_TX003.json   # Texas HO-B (Katy)
├── ingest/
│   ├── crawl.py          # Web crawler for public insurance docs
│   └── chunk.py          # PDF and long-text chunking utilities
└── ui/                   # Next.js 15 + Tailwind v4 frontend
    ├── components/app/   # Welcome screen, voice center, damage worksheet
    ├── hooks/            # useClaimState (data channel), useMossInsuranceEvents
    └── lib/policies.ts   # Policy fixture data for the frontend
```

## Key difference from airline-pnr example

The airline PNR agent queries **one index** per turn (the active booking) and uses `load_index()` per call. This agent:

- Queries **up to three** `SessionIndex` objects in parallel per turn
- Pre-warms **all indexes** at worker start via `prewarm_fnc` — no per-call `load_index()` call
- Adds a **third live index** (the findings session) that grows during the call and is queryable in real time
- Uses **`session.push_index()`** at the end of the call to persist the claim record

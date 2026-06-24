# Insurance Claims Adjuster Voice Agent

A field voice agent for property insurance claims adjusters. Adjusters call in from the inspection site, describe damage, and get instant answers about coverage — hands-free, sub-10ms retrieval.

## What this demonstrates

| Pattern | Description |
|---------|-------------|
| **Multi-index ambient retrieval** | Every adjuster utterance fires TWO Moss queries in parallel — the per-policy index and the shared claims-kb — before the LLM responds. One LLM round-trip per turn. |
| **Per-policyholder index** | Each policy lives in its own `policy-{number}` Moss index. The agent swaps indexes mid-call with `load_policy()`. Same pattern as `examples/voice-agents/airline-pnr`. |
| **On-device embedding** | PII (policyholder name, address, claim history) never leaves the device. Moss embeds locally using the bundled MiniLM model — no external embedding API call. |
| **Web ingestion pipeline** | `ingest/crawl.py` fetches public insurance documentation (iii.org, FEMA, state DOI sites) and chunks it into Moss documents for the shared knowledge base. |
| **Write tools + ambient reads** | Reads are ambient (no tool call, no extra round-trip). Writes use explicit tools: `record_damage_item`, `add_coverage_determination`, `add_field_note`, `submit_claim_report`. |

## Architecture

```
Adjuster utterance
       │
       ▼
on_user_turn_completed (fires BEFORE LLM)
       │
       ├─── asyncio.gather ──────────────────────────────┐
       │                                                  │
       ▼                                                  ▼
Moss query: policy-{number}               Moss query: claims-kb
(declarations, deductibles,               (HO-3 language, exclusions,
 endorsements, prior claims)               state guidelines, water damage
       │                                   distinctions, ACV vs RC)
       │                                                  │
       └──────────────── merge ──────────────────────────┘
                              │
                              ▼
              System message injected into chat context
                              │
                              ▼
                        LLM responds (1 round-trip)
```

## Indexes

| Index | Contents | Scope |
|-------|----------|-------|
| `policy-fl-ho3-001` | FL Cape Coral HO-3: $485K Coverage A, 2% hurricane deductible, water backup + ordinance endorsements | Per-policy |
| `policy-ca-ho3-002` | CA Pasadena HO-3: $620K Coverage A, 50% ordinance endorsement, scheduled jewelry/watches | Per-policy |
| `policy-tx-ho3-003` | TX Katy HO-B: $540K Coverage A, 1% wind/hail deductible, cosmetic damage exclusion | Per-policy |
| `claims-kb` | HO-3 standard policy language, all coverage sections, exclusions, state guidelines (FL/CA/TX), NFIP overview, adjuster workflow | Shared |

## Demo scenarios

After setup, try these queries with each policy:

**FL-HO3-001 (Florida, post-hurricane)**
- "Is the pool cage covered?" → Coverage B, up to $48,500
- "What deductible applies to this wind damage?" → 2% hurricane deductible = $9,700
- "The homeowner says the slab cracked — is that covered?" → Not flood; check if pipe-related
- "Is mold from the water intrusion covered?" → Up to $10,000 sub-limit if from covered peril

**CA-HO3-002 (California, water damage)**
- "Is the earthquake damage covered?" → No, separate CEA policy; give CEA policy number
- "What does the ordinance endorsement cover?" → 50% of Coverage A = $310,000
- "Her engagement ring was stolen — what's the limit?" → Scheduled at $18,500, no deductible
- "The roof is flat — is the leak covered?" → Depends: storm damage covered; ponding/maintenance not

**TX-HO3-003 (Texas, hail)**
- "What's the wind/hail deductible?" → 1% of Coverage A = $5,400
- "The hail dented the roof but didn't compromise it — is that covered?" → Cosmetic exclusion applies
- "The insured wants to invoke appraisal" → Confirm the appraisal clause process
- "Pipes burst in the winter storm — what's covered?" → Covered (sudden/accidental), $5,000 deductible

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

### 3. Build indexes

**Quick start** — use the hand-authored claims KB only (no crawling needed):

```bash
uv run python create_indexes.py
```

**Full pipeline** — crawl public insurance sources first, then build with richer KB:

```bash
# Crawl public sources (~14 pages, ~90 seconds)
uv run python -m ingest.crawl --out data/crawled_kb.json

# Build indexes including crawled docs
uv run python create_indexes.py --include-crawled data/crawled_kb.json
```

List available policy fixtures:

```bash
uv run python create_indexes.py --list
```

Rebuild just the shared KB after a crawl update:

```bash
uv run python create_indexes.py --kb-only --include-crawled data/crawled_kb.json
```

### 4. Run the agent

```bash
uv run python agent.py dev
```

Connect via a LiveKit room at https://agents-playground.livekit.io.

**Optional:** Pre-load a specific policy at startup (skips the policy-number step):

```bash
POLICY_NUMBER=FL-HO3-001 uv run python agent.py dev
```

## Ingestion pipeline

```
ingest/crawl.py      Fetches HTML from iii.org, fema.gov, tdi.texas.gov,
                     insurance.ca.gov, naic.org. Chunks by paragraph with
                     sliding window (≤800 chars). Outputs crawled_kb.json.

ingest/chunk.py      Utilities for PDF ingestion (pdfplumber) and structured
                     policy text chunking. Use this to ingest downloaded
                     policy PDFs from state insurance commissioner sites.
```

### Adding your own policy PDFs

```python
from ingest.chunk import chunk_policy_pdf
import json

docs = chunk_policy_pdf(
    "path/to/state_ho3_form.pdf",
    policy_number="STATE-FORM-2025",
    state="NY",
    source="dfs.ny.gov",
)
# Append to crawled_kb.json or create a new index
json_docs = [{"id": d.id, "text": d.text, "metadata": d.metadata} for d in docs]
```

### Adding your own HTML sources

Edit `ingest/crawl.py` and append to `CRAWL_TARGETS`:

```python
CRAWL_TARGETS.append((
    "https://dfs.ny.gov/consumers/homeowners-insurance",
    "dfs.ny.gov",
    "new_york_homeowners_guide",
))
```

## Project layout

```
insurance-adjuster/
├── agent.py              # LiveKit voice agent (multi-index ambient retrieval)
├── create_indexes.py     # Build per-policy + shared claims-kb indexes
├── pyproject.toml
├── .env.example
├── data/
│   ├── claims_kb.json    # Hand-authored HO-3 policy language (35 documents)
│   └── policies/
│       ├── policy_HO3_FL001.json   # Florida HO-3 (Cape Coral)
│       ├── policy_HO3_CA002.json   # California HO-3 (Pasadena)
│       └── policy_HO3_TX003.json   # Texas HO-B (Katy)
└── ingest/
    ├── crawl.py          # Web crawler for public insurance docs
    └── chunk.py          # PDF and long-text chunking utilities
```

## Key difference from airline-pnr example

The airline PNR agent queries **one index** per turn (the active booking). This agent queries **two indexes in parallel** on every turn and merges both results before the LLM responds:

- Per-policy index → specific facts (this policyholder's Coverage A is $485,000)
- Shared claims-kb → coverage rules (what the 2% hurricane deductible trigger means)

Both arrive in the same context block. The LLM answers with specifics grounded in both layers simultaneously.

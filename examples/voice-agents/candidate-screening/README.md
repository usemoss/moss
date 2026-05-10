# Candidate Screening Voice Agent

Live voice screening interview that grounds every question in **two** Moss
indexes: one for the job description, one for the candidate's resume.

The agent runs a five-phase phone-screen - intro, background verification,
role-fit screening, candidate Q&A, close - and emits a structured **scorecard**
JSON at the end. Both retrievals stay in-process for sub-10ms latency, which
matters because each turn typically needs a JD lookup AND a resume lookup
before the agent can ask a good follow-up.

```
                       ┌──────────────────────┐
   candidate <──────►  │   ScreeningAgent     │ ◄────► scorecard.json
                       │  (one agent, phased) │
                       └──────────┬───────────┘
                                  │
              ┌───────────────────┴───────────────────┐
              ▼                                       ▼
     ┌──────────────────┐                    ┌──────────────────┐
     │  Moss: JD index  │                    │ Moss: resume idx │
     │ (15 docs)        │                    │ (10-12 docs)     │
     └──────────────────┘                    └──────────────────┘
        lookup_job_requirement                lookup_resume_fact
```

## What this example demonstrates

| Capability | Where to look |
|---|---|
| Multi-index retrieval (sub-10ms each) | `agent.py` - `lookup_job_requirement`, `lookup_resume_fact` |
| Adaptive questioning grounded in the resume | `agent.py` - phased system prompt |
| Bias-mitigation rules baked into the prompt + tool surface | `agent.py` - see SYSTEM_PROMPT |
| Consent capture as a real session-state field | `agent.py` - `record_consent`, gated on `submit_scorecard` |
| Live rubric capture (not transcript reconstruction) | `agent.py` - `record_rubric_entry`, `RubricEntry` |
| Structured scorecard artifact | `agent.py` - `_build_scorecard` + `scorecards/*.json` |
| Deterministic eval suite | `evals/test_scorecards.py` |

## Why two indexes

A single combined index would mash JD requirements together with the
candidate's history, and retrieval would conflate them. Two indexes let
the agent ask:

> *"The role calls for Postgres at scale - your resume mentions a logical
> replication migration at Topograph. Walk me through the cutover."*

That sentence requires one query against the JD ("postgres requirement")
and one against the resume ("postgres experience"). With Moss in-process
both happen in single-digit milliseconds, so the LLM gets context before
the candidate notices any pause.

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

3. **Build the two indexes**

   ```bash
   # Default: senior-backend-payments JD + the strong-match candidate
   uv run python create_indexes.py

   # Or pick a different candidate fixture:
   uv run python create_indexes.py --candidate partial
   uv run python create_indexes.py --candidate junior
   uv run python create_indexes.py --list
   ```

   The fixtures live in `data/`. Edit them to point at your own JD or
   candidate, or add new ones.

4. **Run the agent - pick one of two modes**

   ### A) Console mode - talk in your terminal (fastest)

   ```bash
   uv run python agent.py console
   ```

   The agent grabs your mic and speakers directly. Start talking as soon
   as you see the prompt. No LiveKit server, no browser, no frontend.

   ### B) Dev mode - connect from a browser

   ```bash
   uv run python agent.py dev
   ```

   Connect from the [LiveKit Agents Playground](https://agents-playground.livekit.io)
   or a custom React frontend.

## A working interview, condensed

```
Agent:     Hi, I'm calling about your application for the Senior Backend
           Engineer role on the Lattica Payments team. This is a short
           voice screening - about twenty-five minutes. The conversation
           is recorded and reviewed by the hiring team - okay to continue?
Candidate: Yes, that works.
           [calls record_consent(consented=True)]

Agent:     Great. I see from your resume you led the rewrite of the
           settlement pipeline at Northwind Pay - walk me through what
           drove that decision.
           [calls lookup_resume_fact("settlement pipeline rewrite")
            -> "Led the rewrite of Northwind's daily settlement pipeline..."]

Candidate: We were getting 3-5 errors every settlement day, sometimes
           more. The old script had no idempotency, so retries created
           duplicate ledger entries we'd have to manually reconcile...

Agent:     The role also calls for production Postgres at scale - what's
           a non-trivial Postgres incident you've debugged?
           [calls lookup_job_requirement("postgres requirement")
            then lookup_resume_fact("postgres experience")]

           [later, after the answer, calls record_rubric_entry(
              skill="postgres", score=4,
              evidence="Walked through pg_stat_activity lock contention
                       diagnosis and explained the EXPLAIN tradeoff.")]

...

Agent:     Anything you'd like to ask me about the role or the team?
Candidate: What does on-call look like?
           [calls lookup_job_requirement("on-call rotation")
            -> "Required: willingness to participate in an on-call rotation,
               roughly one week every six..."]

Agent:     The team is one-week-on every six. Pages are rare but high-stakes
           when they happen - engineers triage and either fix or escalate
           within fifteen minutes.
           [calls record_candidate_question(
              question="What does on-call look like?",
              answer_summary="1 week in 6, rare pages, 15-min triage SLO")]

Agent:     Thanks, Priya. The team will review your scorecard within
           three business days and reach out about next steps.
           [calls submit_scorecard() -> ./scorecards/strong-match__1234.json]
```

## The scorecard

Written to `scorecards/<candidate_id>__<unix_ts>.json` when the agent calls
`submit_scorecard`:

```json
{
  "candidate_id": "strong-match",
  "role_id": "senior-backend-payments",
  "duration_sec": 1620,
  "rubric": {
    "python":          {"score": 5, "evidence": "..."},
    "postgres":        {"score": 4, "evidence": "..."},
    "payments_domain": {"score": 5, "evidence": "..."},
    "distributed":     {"score": 4, "evidence": "..."},
    "on_call":         {"score": 4, "evidence": "..."}
  },
  "candidate_questions": [
    {"question": "...", "answer_summary": "..."}
  ],
  "notes": [],
  "recommendation": "advance_to_technical",
  "schema_version": 1
}
```

`recommendation` is a rule-of-thumb derived from the rubric; the hiring team
makes the real call.

## Bias mitigation

The system prompt includes an explicit "will not ask, infer, or capture"
list covering protected attributes (age, family status, religion, etc.).
The tool surface is the second line of defence - there is no
`record_protected_attribute` tool, so even if the LLM somehow elicited a
protected fact, the rubric and notes are bounded by what the schemas
allow.

If the candidate volunteers a protected attribute, the agent acknowledges
briefly and moves on without capturing it.

## Running the eval suite

The deterministic parts of the agent (rubric capture, recommendation
rules, scorecard shape) are covered by pytest:

```bash
uv run pytest evals/
```

Eight tests, no LLM or live Moss required. Treat this as the floor -
add scenario tests with real fixtures when you wire CI.

## Files

```text
candidate-screening/
├── agent.py                          # ScreeningAgent + scorecard
├── create_indexes.py                 # Build JD + resume indexes
├── data/
│   ├── job_senior_backend_payments.json
│   ├── candidate_strong_match.json
│   ├── candidate_partial_match.json
│   └── candidate_junior_reach.json
├── evals/
│   └── test_scorecards.py            # Deterministic scorecard tests
├── scorecards/                       # Runtime output (gitignored)
├── pyproject.toml
├── .env.example
└── README.md
```

## Customizing

| Want to change | Edit |
|---|---|
| The role being screened | `data/job_*.json`, then re-run `create_indexes.py` |
| The candidate | `data/candidate_*.json` (or use `--candidate <key>`) |
| Phase timing or rubric | `SYSTEM_PROMPT` in `agent.py` |
| Scorecard schema | `_build_scorecard` and `_recommendation_from_rubric` |
| Voice / latency | STT/LLM/TTS choices in `entrypoint` |

## Resources

- [Moss docs](https://docs.moss.dev)
- [Moss llms.txt](https://moss.dev/llms.txt)
- [LiveKit Agents docs](https://docs.livekit.io/agents/)
- [Moss GitHub](https://github.com/usemoss/moss)
- [Discord](https://discord.com/invite/eMXExuafBR)

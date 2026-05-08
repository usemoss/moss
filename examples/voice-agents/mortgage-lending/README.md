# Mortgage Lending Voice Agent

A multi-agent voice assistant for mortgage servicing, built on
[Moss](https://moss.dev) for sub-10ms retrieval and
[LiveKit Agents](https://docs.livekit.io/agents/) for the realtime voice
pipeline.

The call flows through **two agents** that share state seamlessly:

```
Caller -> [MortgageRetrievalAgent] -- handoff --> [PaymentFlowAgent]
              ^ Moss-backed Q&A                    ^ structured payment
              ^ down payment, FHA, DTI, PMI...     ^ verify -> amount -> method
```

1. **MortgageRetrievalAgent** answers complex, retrieval-heavy questions
   (down payment rules, FHA vs conventional, credit score thresholds, DTI,
   PMI rules, closing costs, required documents). Every factual answer is
   grounded by a Moss query — no hallucinated rates or thresholds.
2. **PaymentFlowAgent** runs a structured payment flow once the customer
   says "I'd like to pay". It reads facts already collected by the first
   agent (loan number, etc.) from shared session state, so the customer
   never has to repeat themselves.

Handoff is one line:

```python
@function_tool
async def transfer_to_payment_flow(self, context: RunContext):
    return PaymentFlowAgent(), "Connecting you to payments now."
```

LiveKit preserves chat history across the switch, so the conversation feels
like one continuous thread to the customer.

## What this example demonstrates

| Capability | Where to look |
|---|---|
| In-process semantic search (sub-10ms) | `agent.py` — `search_mortgage_kb` |
| Multi-agent handoff | `agent.py` — `transfer_to_payment_flow`, `return_to_advisor` |
| Shared session state across agents | `agent.py` — `MortgageSessionData` |
| Knowledge base ingestion | `create_index.py` |

## Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (or `pip` + `venv`)
- A [Moss](https://moss.dev) project (`MOSS_PROJECT_ID`, `MOSS_PROJECT_KEY`)
- A [LiveKit](https://livekit.io) server (or run `livekit-server --dev` locally)
- API keys for your voice providers:
  - [OpenAI](https://platform.openai.com) — LLM
  - [Deepgram](https://deepgram.com) — speech-to-text
  - [Cartesia](https://play.cartesia.ai) — text-to-speech

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

3. **Build the Moss index**

   ```bash
   uv run python create_index.py
   ```

   This loads ~15 mortgage-domain documents into a Moss index named
   `mortgage-lending-kb`. Replace `DOCS` in `create_index.py` with your own
   product sheet to use this in production.

4. **Run the agent**

   ```bash
   uv run python agent.py dev
   ```

   Connect from the [LiveKit Agents Playground](https://agents-playground.livekit.io)
   or [agent-starter-react](https://github.com/livekit-examples/agent-starter-react)
   and start talking.

## Try this conversation

```
Customer: Hi, I'm looking at an FHA loan. What credit score do I need?
Agent:    [calls search_mortgage_kb] FHA goes as low as 500 with 10% down,
          but you'll get a much better rate at 580 or higher with 3.5% down.
Customer: And how much down payment do I need on a conventional loan?
Agent:    [calls search_mortgage_kb] Most conventional loans need at least
          5% down. There are 3% programs for first-time buyers, and 20% down
          removes PMI.
Customer: Got it. Actually, my loan number is 4892017 — I'd like to make
          this month's payment.
Agent:    [calls capture_loan_number, then transfer_to_payment_flow]
          Got it. I have your loan number on file — connecting you to
          payments now.
PaymentAgent: Hi, I'll get your payment set up. I have loan number 4892017
              on file — is that the one you want to pay?
...
```

Notice the customer never has to repeat the loan number after the handoff —
it flows through `MortgageSessionData`.

## How the handoff works

LiveKit Agents 1.0+ supports first-class agent handoff: any `function_tool`
can return either a string (normal tool result) or `(NextAgent, "transition
message")`. When the LLM calls that tool, LiveKit:

1. Runs the optional transition utterance through TTS.
2. Tears down the current agent's tools and instructions.
3. Spins up the new agent with **the same chat history and the same
   `session.userdata`**.
4. Calls the new agent's `on_enter` hook for its first action.

Because both agents read and write the same `MortgageSessionData` dataclass,
state survives the switch without any extra plumbing.

## Files

```text
mortgage-lending/
├── agent.py            # Both agents, shared dataclass, entrypoint
├── create_index.py     # Build the Moss knowledge base
├── pyproject.toml      # uv-managed dependencies
├── .env.example        # Required environment variables
└── README.md           # This file
```

## Resources

- [Moss docs](https://docs.moss.dev)
- [Moss llms.txt](https://moss.dev/llms.txt)
- [LiveKit Agents docs](https://docs.livekit.io/agents/)
- [Moss GitHub](https://github.com/usemoss/moss)
- [Discord](https://moss.link/discord)

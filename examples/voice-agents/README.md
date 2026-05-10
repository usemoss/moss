# Voice Agents

End-to-end voice agent examples that use [Moss](https://moss.dev) for
sub-10ms retrieval inside the speech loop.

| Example | What it shows |
|---|---|
| [`mortgage-lending/`](mortgage-lending/) | Multi-agent flow: a retrieval-heavy mortgage Q&A agent hands off to a payment flow agent, with shared session state. |
| [`candidate-screening/`](candidate-screening/) | Two-index retrieval (job description + candidate resume) powering a live voice screening interview that emits a structured scorecard JSON. Single agent, phased prompt, bias-mitigation rules, deterministic eval suite. |

Each subfolder is self-contained - its own `pyproject.toml`, `.env.example`,
and `README.md`. Pick one, follow its README, and you have a working voice
agent in a few minutes.

## Why Moss for voice

A round-trip to a remote vector database costs 200-500ms - enough to make a
voice conversation feel laggy. Moss runs the retrieval **inside your agent
process**, so the search itself disappears from the latency budget and the
LLM gets grounded context before it speaks.

## Related examples elsewhere in this repo

- [`apps/livekit-moss-vercel/`](../../apps/livekit-moss-vercel/) - single-agent LiveKit voice agent on Vercel.
- [`apps/pipecat-moss/`](../../apps/pipecat-moss/) - Pipecat voice agent with Moss retrieval.
- [`apps/vapi-moss/`](../../apps/vapi-moss/) - Vapi voice agent with Moss retrieval.
- [`apps/elevenlabs-moss/`](../../apps/elevenlabs-moss/) - ElevenLabs voice agent with Moss retrieval.

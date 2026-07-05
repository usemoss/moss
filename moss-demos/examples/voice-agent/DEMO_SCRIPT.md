# Moss Voice Agent — Demo Script (under 2 min)

A tight ~1:45 talking-head + screen-share demo. Talk to a support voice agent while a
live panel shows **Moss** doing the retrieval, then point to the repo.

> Knowledge base is a fictional retailer, **Northwind** (swap in `data/faqs.json`).

## Before you record
- [ ] `livekit-server --dev` running · `python seed_index.py` done · `python agent.py dev` running · `cd web && npm run dev` open at localhost:3000
- [ ] Mic tested, UI on screen (not connected), a **github.com/usemoss/moss** tab ready

---

## 1 · Frame it (0:00–0:12)
> "Let's go through a demo of Moss. This is a customer-support voice agent. The knowledge base is indexed with Moss  — let's start the agent and see how it works."
> and the panel on the right is Moss retrieving them, live and on-device. Watch."

**[Click connect.]**

## 2 · Talk to it (0:12–1:05)

**Q1 — semantic match:**
> "I bought a jacket last week and it doesn't fit. What can I do?"

**[Panel lights up — point to it.]**
> "I never said 'return' or 'refund.' Moss matched the *meaning* — top result, and look
> at the query time: a few milliseconds. The agent answers from that chunk, not thin air."

**Q2 — the wow:**
> "And I think I got charged twice this month."

> "Different question, instant retrieval — it pulled the duplicate-billing policy. Every
> turn is grounded in real data, in real time."

## 3 · Why Moss (1:05–1:35)
> "That was fast because Moss runs the queries **in-process**, right next to the agent — no
> separate vector database, no network round trip. Single-digit milliseconds. And it's
> on-device, so the customer's data never leaves the machine."

## 4 · Hand-off (1:35–1:50)
**[Switch to the GitHub tab.]**
> "Moss is open source, and this whole demo — agent and UI — is in the repo under
> `examples/voice-agent`. Clone it, drop in your own knowledge base, and you've got a
> grounded voice agent running locally. Go build something using moss."

---

## Backup questions (swap in if needed)
- "How long until my order shows up?" → shipping times
- "I forgot my password." → account access
- "Does it break down after a couple months — any coverage?" → warranty

## Three points to hit (if you freestyle)
1. In-process, no network hop → single-digit ms
2. On-device → data stays private
3. Open source → clone and build

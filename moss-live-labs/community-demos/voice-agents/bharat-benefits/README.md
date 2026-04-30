# 🇮🇳 Bharat Benefits Voice Agent

> **[Live Lab Demo]** A voice-first RAG assistant for Indian public-benefit schemes, built with
> **Moss** semantic retrieval and **Sarvam AI** speech APIs.

---

## What This Demo Does

Bharat Benefits Voice Agent lets users ask questions — by voice or text — about Indian government
welfare schemes and receive spoken, grounded answers in return.

**Demo flow:**

```
User voice / text input
    ↓
Sarvam STT  (saaras:v3)         – converts speech to text
    ↓
Moss retrieval                  – finds relevant scheme snippets from local markdown KB
    ↓
Sarvam Chat Completion          – generates a grounded, voice-friendly answer
    ↓
Sarvam TTS  (bulbul:v3)         – converts the answer to speech
    ↓
response.wav  (saved + played)  – spoken answer delivered to user
```

The knowledge base covers five schemes:
- **Ayushman Bharat / PM-JAY** – health insurance for poor families
- **PM-KISAN** – income support for small farmers
- **PM Vishwakarma** – skill and financial support for artisans
- **National Scholarship Portal** – centralised scholarship access for students
- **PMKVY / Skill India** – free vocational skill training and certification

> ⚠️ **Disclaimer**: This is a demo knowledge base, not an official government service.
> All scheme information is curated for demonstration purposes. Always verify eligibility,
> amounts, and deadlines on the official government portals listed in each scheme file.

---

## Why Moss?

Moss is a real-time semantic search runtime designed for conversational AI agents. Instead of a
heavy vector database, Moss gives you:

- Sub-10 ms retrieval — fast enough to fit inside a live voice conversation turn.
- A simple SDK: `create_index` → `load_index` → `query`. No cluster management.
- Hybrid search (semantic + keyword) with a single `alpha` parameter.
- Cloud sync: index once, load anywhere.

In this demo, Moss retrieves the top-3 most relevant scheme snippets for the user's question,
which are then passed as grounded context to the LLM — preventing hallucination of eligibility
rules, amounts, or deadlines.

### Moss SDK methods used

| Method | Why it's used here |
|---|---|
| `MossClient(project_id, project_key)` | Initialise the client with credentials |
| `client.create_index(name, documents)` | Index all scheme markdown files once |
| `client.load_index(name)` | Load the index into the local search runtime before querying |
| `client.query(name, question, QueryOptions(top_k=3, alpha=0.75))` | Retrieve top-3 relevant scheme snippets; `alpha=0.75` blends semantic (75%) and keyword (25%) search |

---

## Why Sarvam?

Sarvam AI is India's purpose-built AI stack for Indian languages. It provides:

- **Saaras v3 (STT)**: State-of-the-art speech-to-text with support for 23 languages including
  Hindi, Bengali, Tamil, Telugu, Punjabi, and more — perfect for India-first voice apps.
- **Sarvam-30B / 105B (Chat)**: Multilingual chat models that understand Indian
  linguistic context.
- **Bulbul v2/v3 (TTS)**: Natural-sounding Indian-language voices for generating spoken responses.

This combination means the demo can handle queries in multiple Indian languages out of the box,
making it genuinely accessible to beneficiaries across the country.

---

## Setup Instructions

### 1. Clone / navigate to the demo folder

```bash
cd moss-live-labs/community-demos/voice-agents/bharat-benefits/
```

### 2. Create a Python virtual environment (recommended)

```bash
python -m venv .venv
source .venv/bin/activate          # Linux / macOS
# .venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> On some systems `simpleaudio` (audio playback) may require system build tools.
> If it fails to install, the bot still works — it just saves `response.wav` without auto-playing.
> On Debian/Ubuntu: `sudo apt-get install libasound2-dev`

### 4. Set up environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in:

| Variable | Where to get it |
|---|---|
| `SARVAM_API_KEY` | [dashboard.sarvam.ai](https://dashboard.sarvam.ai) |
| `MOSS_PROJECT_ID` | [moss.dev](https://moss.dev) |
| `MOSS_PROJECT_KEY` | [moss.dev](https://moss.dev) |

The other variables (`SARVAM_STT_MODEL`, etc.) have sensible defaults — you only need to change
them if you want to experiment with different model versions.

### 5. Create the Moss index

Run this **once** to read the scheme markdown files and index them in Moss:

```bash
python create_index.py
```

Expected output:

```
📂 Loading scheme documents from: data/schemes/
   Found 5 file(s):
   • ayushman-bharat.md
   • national-scholarship-portal.md
   • pm-kisan.md
   • pm-vishwakarma.md
   • pmkvy-skill-india.md

🔨 Creating Moss index 'bharat-benefits' …
✅ Index 'bharat-benefits' created successfully with 5 document(s).
```

---

## Running the Bot

```bash
# Live mic mode (default 5 seconds per turn)
python bot.py

# Longer recording window
python bot.py --seconds 8

# Debug without mic (type questions)
python bot.py --text-mode

### Audio file mode

Pass a pre-recorded WAV or MP3 file:

```bash
python bot.py --audio path/to/question.wav
```

### Microphone mode

Record live from your default microphone:

```bash
python bot.py --seconds 5
```

### Interactive mode (no arguments)

```bash
python bot.py
```

The bot will start recording from your microphone. Use `--text-mode` to type questions instead.

---

## Example Demo Questions

| Question | Relevant scheme(s) |
|---|---|
| "I am a small farmer. Which scheme can help me?" | PM-KISAN |
| "What documents are usually needed for Ayushman Bharat?" | Ayushman Bharat |
| "Explain PM Vishwakarma in simple Hindi-English." | PM Vishwakarma |
| "Which scheme is useful for skill training?" | PMKVY / Skill India |
| "I am a student looking for scholarship support. Where should I start?" | NSP |
| "I am a carpenter. Is there any government scheme for me?" | PM Vishwakarma |
| "How much money does PM-KISAN give, and how often?" | PM-KISAN |
| "What is the health benefit under PM-JAY?" | Ayushman Bharat |
| "I want free vocational training. What should I do?" | PMKVY |
| "My family is poor and needs medical coverage. Help." | Ayushman Bharat |

---

## Required Environment Variables

```
SARVAM_API_KEY          # Sarvam AI subscription key (required)
MOSS_PROJECT_ID         # Moss project ID (required)
MOSS_PROJECT_KEY        # Moss project key (required)
MOSS_INDEX_NAME         # Index name, default: bharat-benefits (optional)
SARVAM_STT_MODEL        # STT model, default: saaras:v3 (optional)
SARVAM_CHAT_MODEL       # Chat model, default: sarvam-30b/105-b (optional)
SARVAM_TTS_MODEL        # TTS model, default: bulbul:v3 (optional)
SARVAM_TTS_SPEAKER      # TTS speaker voice, default: priya (optional)
```

---

## Folder Structure

```
bharat-benefits/
├── README.md              ← this file
├── .env.example           ← copy to .env and fill in credentials
├── requirements.txt       ← Python dependencies
├── create_index.py        ← one-time Moss index creation script
├── bot.py                 ← main voice agent (STT → Moss → LLM → TTS)
└── data/
    └── schemes/
        ├── ayushman-bharat.md
        ├── pm-kisan.md
        ├── pm-vishwakarma.md
        ├── national-scholarship-portal.md
        └── pmkvy-skill-india.md
```

---

## Limitations / Disclaimer

- **Demo knowledge base only.** The scheme information in `data/schemes/` is curated for
  demonstration purposes and may not reflect the latest government guidelines, benefit amounts,
  or eligibility criteria.
- **Not an official government service.** This agent cannot process applications, verify
  beneficiary status, or access real-time government databases.
- **Always verify on official portals:**
  - Ayushman Bharat: https://pmjay.gov.in
  - PM-KISAN: https://pmkisan.gov.in
  - PM Vishwakarma: https://pmvishwakarma.gov.in
  - National Scholarship Portal: https://scholarships.gov.in
  - Skill India / PMKVY: https://www.skillindia.gov.in
- **Audio playback** requires `simpleaudio`; if unavailable, `response.wav` is saved to disk.
- **Microphone recording** requires `sounddevice` and `soundfile`; use `--text` or `--audio` as
  fallback.
- **Language**: The LLM answer is generated in English by default. For Indic-language answers,
  consider switching `target_language_code` in the TTS call and adjusting the system prompt.

---

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| `moss` | ≥1.0.0 | Moss semantic search SDK |
| `python-dotenv` | ≥1.0.0 | Load `.env` credentials |
| `httpx` | ≥0.27.0 | Async-friendly HTTP for Sarvam API calls |
| `sounddevice` | ≥0.4.6 | Microphone recording |
| `soundfile` | ≥0.12.1 | WAV file I/O |
| `simpleaudio` | ≥1.0.4 | Audio playback (optional) |
| `numpy` | ≥1.26.0 | Audio array support |

---



*Built for the Moss Live Labs community. Contributions and improvements welcome.*

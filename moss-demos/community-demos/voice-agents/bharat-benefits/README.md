# Bharat Benefits Voice Agent

A voice-first RAG assistant for Indian public-benefit schemes, built with
Moss semantic retrieval and Sarvam AI speech APIs.

---

## What This Does

Users ask questions by voice or text about Indian government welfare schemes
and receive spoken, grounded answers in return.

```
voice / text input
    |
Sarvam STT  (saaras:v3)         converts speech to text
    |
Moss retrieval                  finds relevant scheme snippets from local knowledge base
    |
Sarvam Chat Completion          generates a grounded, voice-friendly answer
    |
Sarvam TTS  (bulbul:v3)         converts the answer to speech
    |
audio response                  played back through speakers
```

The knowledge base covers five schemes:

- Ayushman Bharat / PM-JAY - health insurance for poor families
- PM-KISAN - income support for small farmers
- PM Vishwakarma - skill and financial support for artisans
- National Scholarship Portal - centralised scholarship access for students
- PMKVY / Skill India - free vocational skill training and certification

> This is a demo knowledge base, not an official government service. Always
> verify eligibility, amounts, and deadlines on the official government portals
> listed in each scheme file.

---

## Recording Modes

The agent supports three input modes:

**Fixed window (default)**
Records for a set number of seconds per turn. Simple and predictable.

```bash
python bot.py              # 5 seconds per turn
python bot.py --seconds 8  # 8 seconds per turn
```

**VAD mode** (recommended for natural conversation)
Uses voice activity detection to automatically stop recording when you
pause speaking. No need to worry about a timer — just speak naturally and
the agent picks up when you stop.

```bash
python bot.py --vad
```

**Text mode** (for debugging)
Type questions instead of speaking. Useful when testing without a microphone.

```bash
python bot.py --text-mode
```

---

## Why Moss?

Moss is a real-time semantic search runtime for conversational AI agents.

- Sub-10 ms retrieval, fast enough for a live voice turn.
- Simple SDK: `create_index` then `load_index` then `query`. No cluster to manage.
- Hybrid search (semantic + keyword) with a single `alpha` parameter.
- Cloud sync: index once, load anywhere.

Moss retrieves the top-3 most relevant scheme snippets for each question,
which are passed as grounded context to the LLM. This prevents hallucination
of eligibility rules, amounts, or deadlines.

### Moss SDK methods used

| Method | Purpose |
|---|---|
| `MossClient(project_id, project_key)` | Initialise the client |
| `client.create_index(name, documents)` | Index scheme files (run once) |
| `client.load_index(name)` | Load index into local runtime before querying |
| `client.query(name, question, QueryOptions(top_k=3, alpha=0.75))` | Retrieve top-3 relevant snippets |

`alpha=0.75` blends 75% semantic search with 25% keyword search.

---

## Why Sarvam?

Sarvam AI is India's purpose-built AI stack for Indian languages.

- Saaras v3 (STT): speech-to-text with support for 23 Indian languages including
  Hindi, Bengali, Tamil, Telugu, Punjabi, and more.
- Sarvam-30B / 105B (Chat): multilingual chat models with Indian linguistic context.
- Bulbul v2/v3 (TTS): natural-sounding Indian-language voices.

The combination handles queries in multiple Indian languages out of the box.

---

## Setup

### 1. Navigate to the demo folder

```bash
cd moss-live-labs/community-demos/voice-agents/bharat-benefits/
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate          # Linux / macOS
# .venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

On Debian/Ubuntu, if `simpleaudio` fails to build:
```bash
sudo apt-get install libasound2-dev
```

`webrtcvad` is only required for `--vad` mode. If you don't need it, the
rest of the agent works without it.

### 4. Set environment variables

```bash
cp .env.example .env
```

Fill in:

| Variable | Where to get it |
|---|---|
| `SARVAM_API_KEY` | dashboard.sarvam.ai |
| `MOSS_PROJECT_ID` | moss.dev |
| `MOSS_PROJECT_KEY` | moss.dev |

The other variables have sensible defaults.

### 5. Create the Moss index (run once)

```bash
python create_index.py
```

Expected output:

```
Loading scheme documents from: data/schemes/
Found 5 file(s):
  ayushman-bharat.md
  national-scholarship-portal.md
  pm-kisan.md
  pm-vishwakarma.md
  pmkvy-skill-india.md

Creating Moss index 'bharat-benefits' ...
Index 'bharat-benefits' created with 5 document(s).
```

---

## Running the Agent

```bash
# Fixed window, 5 seconds per turn (default)
python bot.py

# Fixed window, custom duration
python bot.py --seconds 8

# VAD mode - stops when you pause (most natural)
python bot.py --vad

# Text mode - type questions (no mic needed)
python bot.py --text-mode
```

---

## Example Questions

| Question | Relevant scheme |
|---|---|
| "I am a small farmer. Which scheme can help me?" | PM-KISAN |
| "What documents are needed for Ayushman Bharat?" | Ayushman Bharat |
| "I am a carpenter. Is there any government scheme for me?" | PM Vishwakarma |
| "How much money does PM-KISAN give, and how often?" | PM-KISAN |
| "I want free vocational training. What should I do?" | PMKVY |
| "My family is poor and needs medical coverage." | Ayushman Bharat |
| "I am a student looking for scholarship support." | NSP |
| "Which scheme is useful for skill training?" | PMKVY / Skill India |

---

## Environment Variables

```
SARVAM_API_KEY          Sarvam AI subscription key (required)
MOSS_PROJECT_ID         Moss project ID (required)
MOSS_PROJECT_KEY        Moss project key (required)
MOSS_INDEX_NAME         Index name, default: bharat-benefits (optional)
SARVAM_STT_MODEL        STT model, default: saaras:v3 (optional)
SARVAM_CHAT_MODEL       Chat model, default: sarvam-105b (optional)
SARVAM_TTS_MODEL        TTS model, default: bulbul:v3 (optional)
SARVAM_TTS_SPEAKER      TTS speaker voice, default: priya (optional)
```

---

## Folder Structure

```
bharat-benefits/
├── README.md
├── .env.example
├── requirements.txt
├── create_index.py        one-time Moss index creation
├── bot.py          main voice agent (STT -> Moss -> LLM -> TTS)
└── data/
    └── schemes/
        ├── ayushman-bharat.md
        ├── pm-kisan.md
        ├── pm-vishwakarma.md
        ├── national-scholarship-portal.md
        └── pmkvy-skill-india.md
```

---

## Limitations

- Demo knowledge base only. Scheme information may not reflect the latest
  government guidelines, benefit amounts, or eligibility criteria.
- Not an official government service. Cannot process applications, verify
  beneficiary status, or access real-time government databases.
- Audio playback requires `simpleaudio`. If unavailable, audio is saved to disk.
- VAD mode requires `webrtcvad`. Falls back to fixed-window if not installed.

Official portals for verification:

- Ayushman Bharat: https://pmjay.gov.in
- PM-KISAN: https://pmkisan.gov.in
- PM Vishwakarma: https://pmvishwakarma.gov.in
- National Scholarship Portal: https://scholarships.gov.in
- Skill India / PMKVY: https://www.skillindia.gov.in

---

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| `moss` | >=1.0.0 | Moss semantic search SDK |
| `python-dotenv` | >=1.0.0 | Load .env credentials |
| `httpx` | >=0.27.0 | HTTP client for Sarvam API calls |
| `sounddevice` | >=0.4.6 | Microphone recording and playback |
| `soundfile` | >=0.12.1 | WAV file read/write |
| `simpleaudio` | >=1.0.4 | Audio playback (optional) |
| `numpy` | >=1.26.0 | Audio array handling |
| `webrtcvad` | >=2.0.10 | Voice activity detection for --vad mode (optional) |

---

Built for the Moss Live Labs community.
# Multi-Tenant Index Routing with Moss

A LangChain + OpenAI agent that serves **five different businesses** from a single codebase — no hard-coded routing, no system prompt swapping.

Each business has its own named Moss index. The agent exposes one search tool per index. GPT-4.1-mini reads the tool names and descriptions, decides which index(es) to query, and synthesises the answer. For ambiguous questions it calls multiple indexes in parallel and merges the results.

---

## What's in This Cookbook

| File | Purpose |
| ---- | ------- |
| `moss_multitenant.py` | `IndexStore` (lazy per-index loading) + `build_tools` (generates one LangChain `StructuredTool` per index) |
| `agent.py` | `MultiTenantAgent` — `llm.bind_tools()` + minimal async loop, no framework overhead |
| `data/*.json` | Sample knowledge bases — 10 documents each for 5 businesses |

### The five indexes

| Index name | Business | Domain |
| ---------- | -------- | ------ |
| `food-luigis-pizzeria` | Luigi's Pizzeria | Menu, prices, delivery, hours |
| `law-harrison-cole` | Harrison & Cole LLP | Legal fees, practice areas, consultations |
| `tech-stackbase` | Stackbase | SaaS pricing, API, onboarding |
| `health-vitacare` | VitaCare Clinic | Medical services, appointments, insurance |
| `retail-urban-threads` | Urban Threads | Clothing catalog, returns, shipping |

---

## Prerequisites

- Python 3.11+
- A [Moss](https://moss.dev) account — get `MOSS_PROJECT_ID` and `MOSS_PROJECT_KEY` from the dashboard
- An OpenAI API key

---

## Setup

### 1. Navigate to the cookbook

```bash
cd examples/cookbook/multi-tenant
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -e .
```

### 4. Configure credentials

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```bash
MOSS_PROJECT_ID=your-project-id
MOSS_PROJECT_KEY=your-project-key
OPENAI_API_KEY=your-openai-api-key
```

---

## Running

### Full demo

Runs a set of questions across all five businesses and prints which index(es) the agent searched plus the final answer for each.

```bash
python agent.py
```

On first run this creates the five Moss indexes from the data files. Subsequent runs skip creation automatically.

### Single question

```bash
# Clear single-index routing
python agent.py --q "Do you offer gluten-free pizza?"
python agent.py --q "What are the hourly legal fees?"
python agent.py --q "How do I get started with the free plan?"
python agent.py --q "Can I book a telehealth appointment on a Saturday?"
python agent.py --q "What is your return policy for online orders?"

# Ambiguous — agent searches multiple indexes and merges the answer
python agent.py --q "What are your opening hours?"
python agent.py --q "I'm starting a food business. What legal structure do I need and where can I get lunch?"
```

---

## How Routing Works

There is no `if/else` routing logic anywhere in the code. The only signal the model uses is the tool name and description:

```text
search_food_luigis_pizzeria   → "pizza, menu, toppings, food questions"
search_law_harrison_cole      → "legal, attorney, contracts"
search_tech_stackbase         → "SaaS, API, developer tools"
search_health_vitacare        → "medical, clinic, doctor"
search_retail_urban_threads   → "clothing, retail, fashion"
```

GPT-4.1-mini picks which tool(s) to call. The agent executes them concurrently via `asyncio.gather`, Moss returns the top-5 docs from each queried index in <10ms, and the model synthesises the final answer — all in a tight `bind_tools` + `ainvoke` loop with no graph or executor overhead.

Indexes load lazily — only the ones the model actually calls are loaded from Moss cloud. If a question clearly targets one business, the other four indexes are never touched.

---

## Adding a New Business

**1.** Add a JSON file to `data/`:

```json
[
  {
    "id": "unique-doc-id",
    "text": "The content the model will see when this document is retrieved.",
    "metadata": {}
  }
]
```

**2.** Add an entry to `BUSINESSES` in `agent.py`:

```python
"finance-acme-bank": {
    "name": "Acme Bank",
    "data_file": "acme_bank.json",
    "tool_description": (
        "Search Acme Bank knowledge base. Covers account types, interest rates, "
        "loan products, and branch hours. Use for banking or finance questions."
    ),
},
```

**3.** Run `python agent.py` — the new index is created and its tool registered automatically.

---

## Dependencies

```text
moss>=1.0.0       — semantic search, on-device, sub-10ms
langchain-core    — StructuredTool + message types (HumanMessage, ToolMessage, ...)
langchain-openai  — ChatOpenAI + bind_tools
python-dotenv     — .env credential loading
```

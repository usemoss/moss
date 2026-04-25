# Moss Portal Quickstart

Get from zero to your first query in under 5 minutes.

**Prerequisites:** Node.js 18+ or Python 3.10+

---

## 1. Sign in to the portal

Open [portal.usemoss.dev](https://portal.usemoss.dev) and sign in. You'll land straight in the **Create your first index** onboarding dialog.

## 2. Create your first index

In the onboarding dialog:

1. **Index name**: give it something memorable (e.g. `demo`).
2. **Model**: leave as **MOSS Mini LM** (faster responses, <10ms, great for real-time apps).
3. Under the cards, pick **Search → Get started** (option 1). This spins up an index pre-populated with curated FAQ documents so you can query immediately.

> Already past onboarding? From the dashboard, find the **1-click sample** card under Search Indexes and hit **Use sample FAQs**.

## 3. Copy your credentials

In the left sidebar, go to **Settings → API Keys**. You'll see:

- **Project ID**: a UUID, safe to expose.
- **Project Key**: secret. Never commit this or expose it client-side.

Scroll down to **Environment Variables** and hit **Copy** on the `.env` block. You'll get something like:

```bash
MOSS_PROJECT_ID=f79fb46d-c42d-4da3-a903-803322ae7f0e
MOSS_PROJECT_KEY=moss_k2n********************************
```

Paste this into a `.env` file at the root of your project. Add `.env` to `.gitignore`.

> Shortcut: on the dashboard there's a **CLI one-liner** card with a **Copy CLI snippet** button that exports both env vars and runs the quickstart script in one go. Handy if you just want to see it work in your terminal before wiring it into an app.

## 4. Install the SDK

```bash
# JavaScript / TypeScript
npm install @moss-dev/moss dotenv

# Python
pip install moss python-dotenv
```

## 5. Load the index and query it

Since the index was created from the portal, your code only needs to **load** it and **query** it.

**TypeScript** (`quickstart.ts`):

```ts
import 'dotenv/config'
import { MossClient } from '@moss-dev/moss'

const client = new MossClient(
  process.env.MOSS_PROJECT_ID!,
  process.env.MOSS_PROJECT_KEY!,
)

const indexName = 'demo' // whatever you named it in the portal

await client.loadIndex(indexName)

const results = await client.query(
  indexName,
  'How do I return a damaged product?',
  { topK: 3 },
)

console.log(results.docs[0])
```

Run it:

```bash
npx tsx quickstart.ts
```

**Python** (`quickstart.py`):

```python
import os
import asyncio
from dotenv import load_dotenv
from moss import MossClient, QueryOptions

load_dotenv()

client = MossClient(
    os.getenv("MOSS_PROJECT_ID"),
    os.getenv("MOSS_PROJECT_KEY"),
)

index_name = "demo"  # whatever you named it in the portal

async def main():
    await client.load_index(index_name)
    results = await client.query(
        index_name,
        "How do I return a damaged product?",
        QueryOptions(top_k=3),
    )
    top = results.docs[0]
    print(f"ID:    {top.id}")
    print(f"Score: {top.score}")
    print(f"Text:  {top.text}")

asyncio.run(main())
```

Run it:

```bash
python quickstart.py
```

### Expected output

```json
{
  "id": "doc2",
  "score": 0.88,
  "text": "What is your return policy? We offer a 30-day return policy for most items."
}
```

That's it. You're live.

---

## Bringing your own data

From the dashboard, Search Indexes:

- **Upload JSON**: drop a JSON array of `{ id, text, metadata? }` objects and click **Upload & create**.
- **Search** (during onboarding): wire up semantic search across your app or website content.

Or create an index from code:

```python
from moss import DocumentInfo

documents = [
    DocumentInfo(id="doc1", text="...", metadata={"category": "shipping"}),
    DocumentInfo(id="doc2", text="...", metadata={"category": "returns"}),
]

await client.create_index(index_name, documents, "moss-minilm")
# swap in "moss-mediumlm" for higher accuracy
```

---

## Next steps

- Explore metadata filters and `topK` tuning in `client.query(...)`.
- Full reference: [docs.moss.dev](https://docs.moss.dev)
- Community: [Join us on Discord](https://discord.com/invite/eMXExuafBR)

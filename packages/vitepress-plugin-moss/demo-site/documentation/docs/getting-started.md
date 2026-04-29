# Getting started

Moss is a high-performance runtime for real-time semantic search. It delivers sub-10 ms lookups, instant index updates, and zero infrastructure overhead. Moss runs where your agent lives — cloud, in-browser, or on-device — so search feels native and users never wait.

**[View samples on GitHub](https://github.com/usemoss/moss-samples)** | **[Join our Discord](https://discord.gg/eMXExuafBR)**

---

## Create an account

Visit [Moss Portal](https://usemoss.dev/) to create an account, confirm your email, and sign in.

Inside the default project you will see two plans:

| Plan | Includes |
| --- | --- |
| **Free** | 1 project, 3 indexes, 1,000 items per index, community support |
| **Developer Workspace** | Unlimited projects and indexes, 100 GB storage, 100 GB ingestion, 1 TB egress, priority support |

Enter valid card details to start the free trial, then select **Create Index** to provision a new index.

> ![Moss Portal walkthrough](https://github.com/user-attachments/assets/c3db9d2d-0df5-4cec-99fd-7d49d0a30844)

---

## 1. Install the SDK

::: code-group

```bash [JavaScript]
npm install @moss-dev/moss-web
```

```bash [Python]
pip install moss
```

:::

## 2. Configure credentials

Grab your **Project ID** and **Project Key** from the Moss console. Store them as environment variables so both clients can reuse them.

```bash
# .env
MOSS_PROJECT_ID="your-project-id"
MOSS_PROJECT_KEY="your-project-key"
```

Or export them in your shell:

```bash
export MOSS_PROJECT_ID="your-project-id"
export MOSS_PROJECT_KEY="your-project-key"
```

## 3. Create an index and query

::: code-group

```ts [JavaScript]
import { MossClient, DocumentInfo } from '@moss-dev/moss-web'

const client = new MossClient(
  process.env.MOSS_PROJECT_ID!,
  process.env.MOSS_PROJECT_KEY!
)

await client.createIndex(
  'support-faqs',
  [
    { id: '1', text: 'Track an order from the dashboard.' },
    { id: '2', text: 'Return window lasts 30 days.' }
  ],
  'moss-minilm'
)

await client.loadIndex('support-faqs')
const response = await client.query('support-faqs', 'How do I track my order?')
console.log(response.docs[0])
```

```py [Python]
import asyncio
from moss import MossClient, DocumentInfo

client = MossClient("$MOSS_PROJECT_ID", "$MOSS_PROJECT_KEY")

async def main():
    await client.create_index(
        "support-faqs",
        [
            DocumentInfo(id="1", text="Track an order from the dashboard."),
            DocumentInfo(id="2", text="Return window lasts 30 days."),
        ],
        "moss-minilm",
    )

    await client.load_index("support-faqs")
    results = await client.query("support-faqs", "How do I track my order?")
    print(results.docs[0])

asyncio.run(main())
```

:::

## 4. Tailor retrieval

- **Choose a model** — start with `moss-minilm` for balanced performance, or switch to a larger embedding model for higher recall.
- **Batch updates** — use `addDocs` / `add_docs` to append new knowledge as your content changes.

---

## Sample code

The [samples repository](https://github.com/usemoss/moss-samples) contains working examples covering authentication, batch context, and streaming replies.

### Python samples

| Sample | Description |
| --- | --- |
| [`comprehensive_sample.py`](https://github.com/usemoss/moss-samples/blob/main/python/comprehensive_sample.py) | End-to-end flow with session creation, context building, and streaming |
| [`load_and_query_sample.py`](https://github.com/usemoss/moss-samples/blob/main/python/load_and_query_sample.py) | Ingest domain knowledge before querying |

```bash
pip install -r python/requirements.txt
python python/comprehensive_sample.py
```

> ![Moss Python walkthrough](https://github.com/user-attachments/assets/d826023d-92d6-49ac-8e5e-81cf04d409c5)

### JavaScript samples

| Sample | Description |
| --- | --- |
| [`comprehensive_sample.ts`](https://github.com/usemoss/moss-samples/blob/main/javascript/comprehensive_sample.ts) | Full workflow in TypeScript, ready for Node |
| [`load_and_query_sample.ts`](https://github.com/usemoss/moss-samples/blob/main/javascript/load_and_query_sample.ts) | Index FAQs and issue targeted queries |

```bash
cd javascript && npm install
npm run start -- comprehensive_sample.ts
```

---

## Next steps

- Dive deeper into the [JavaScript SDK](/reference/js/README.md) and [Python SDK](/reference/python/README.md) references.
- Check out the [Moss YC Launch Post](https://www.ycombinator.com/launches/Oiq-moss-real-time-semantic-search-for-conversational-ai).

If you spot gaps or want another language example, open an issue or PR in the [samples repository](https://github.com/usemoss/moss-samples).

# Getting Started

Moss is a high-performance runtime for real-time semantic search. It delivers sub-10 ms lookups, instant index updates, and zero infra overhead. Moss runs where your agent lives - cloud, in-browser, or on-device - so search feels native and users never wait. You connect your data once; Moss handles indexing, packaging, distribution and updates.

**📦 [View Samples Repository on GitHub](https://github.com/usemoss/moss-samples)**

**Join our [discord server](https://discord.gg/eMXExuafBR) to get onboarded!**

## Using Moss Portal

Visit [Moss](https://usemoss.dev/) to create an account, confirm your email, and sign in.

Inside the default project you will see two plans:

- **Free Tier ($0)** offers 1 project, 3 indexes, and 1,000 items per index with community support;
- **Developer Workspace ($2000/month + usage)** adds unlimited projects/indexes plus 100 GB storage, 100 GB ingestion, 1 TB egress, and priority support.

Enter valid card details to start the free trial, then select **Create Index** to provision a new index.

> ![Moss Portal walkthrough](https://github.com/user-attachments/assets/c3db9d2d-0df5-4cec-99fd-7d49d0a30844)

## 1. Install the SDK

::: code-group

```bash [JS/TS]
npm install @inferedge/moss
```

```bash [Python]
pip install inferedge-moss
```

:::

## 2. Configure credentials

Grab your **Project ID** and **Project Key** from the Moss console. Store them as environment variables so both clients can reuse them.

### Create a .env file

Create a `.env` file in your project root directory and add your credentials:

```bash
MOSS_PROJECT_ID="your-project-id"
MOSS_PROJECT_KEY="your-project-key"
```

Alternatively, you can export them in your terminal session:

```bash
export MOSS_PROJECT_ID="your-project-id"
export MOSS_PROJECT_KEY="your-project-key"
```

## 3. Create an index and run a query

Launch your first Moss index and query in minutes. Whether you are building a browser app or a Python service, the code below gets you from credentials to live search results.

::: code-group

```ts [JavaScript]
import { MossClient, DocumentInfo } from '@inferedge/moss'

const client = new MossClient(process.env.MOSS_PROJECT_ID!, process.env.MOSS_PROJECT_KEY!)

await client.createIndex(
  'support-faqs',
  [
    { id: '1', text: 'Track an order from the dashboard.' },
    { id: '2', text: 'Return window lasts 30 days.' }
  ],
  'moss-minilm'
)

await client.loadIndex("support-faqs")
const response = await client.query('support-faqs', 'How do I track my order?')
console.log(response.docs[0])
```

```py [Python]
import asyncio
from inferedge_moss import MossClient, DocumentInfo

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

## Explore Sample Code

The [samples repository](https://github.com/usemoss/moss-samples) contains working examples that show how to authenticate, batch context, and stream replies without extra boilerplate. Adapt the scripts by swapping the FAQ JSON files with your data, or plugging Moss calls into an existing app.

### Python SDK Samples

- [`python/comprehensive_sample.py`](https://github.com/usemoss/moss-samples/blob/main/python/comprehensive_sample.py): end-to-end flow with session creation, context building, and streaming responses.
- [`python/load_and_query_sample.py`](https://github.com/usemoss/moss-samples/blob/main/python/load_and_query_sample.py): how to ingest domain knowledge before querying Moss.

- Install deps with `pip install -r python/requirements.txt`, then run any script via `python path/to/sample.py`.

> ![Moss Python walkthrough](https://github.com/user-attachments/assets/d826023d-92d6-49ac-8e5e-81cf04d409c5)

### JavaScript SDK Samples

- [`javascript/comprehensive_sample.ts`](https://github.com/usemoss/moss-samples/blob/main/javascript/comprehensive_sample.ts): TypeScript version of the full workflow, ready for Node.
- [`javascript/load_and_query_sample.ts`](https://github.com/usemoss/moss-samples/blob/main/javascript/load_and_query_sample.ts): demonstrates indexing FAQs and issuing targeted prompts.

- Install deps with `npm install` inside `javascript/`, then execute via `npm run start -- path/to/sample.ts`.

## Next Steps

- Dive deeper into the [JavaScript SDK](/reference/js/README.md) and [Python SDK](/reference/python/README.md) guides.
- Explore the API references for [JavaScript](/reference/js/globals.md) and [Python](/reference/python/globals.md) for every method and data type.
- Check out our [Launch YC Post!](https://www.ycombinator.com/launches/Oiq-moss-real-time-semantic-search-for-conversational-ai)

If you spot gaps or want another language example, open an issue or PR in the [samples repository](https://github.com/usemoss/moss-samples). We track feedback closely.

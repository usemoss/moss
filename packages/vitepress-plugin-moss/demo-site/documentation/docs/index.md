---
layout: home
search: false

hero:
  name: "Moss Client SDKs"
  text: ""
  tagline: "Sub-10 ms retrieval for conversational AI, voice assistants, and multimodal agents. On-device, in-browser, or in the cloud."
  actions:
    - theme: brand
      text: Get started
      link: /getting-started
    - theme: alt
      text: JavaScript SDK
      link: /reference/js/README.md
    - theme: alt
      text: Python SDK
      link: /reference/python/README.md

features:
  - title: Zero-hop latency
    details: Retrieval from device memory in under 10 ms. No round-trip to a server. Answers feel instant.
  - title: Model-agnostic
    details: Works with any embedding model. Bring your own vectors or use the built-in defaults. No vendor lock-in.
  - title: Offline-first, cloud-smart
    details: Runs entirely offline with optional cloud sync for backups, analytics, and multi-device distribution.
---

## Why Moss

Moss is a high-performance runtime for real-time semantic search. It delivers sub-10 ms retrieval, instant index updates, and zero infrastructure overhead. It runs wherever your intelligence lives — in-browser, on-device, or in the cloud — so search feels native and effortless.

::: tip
Head to [Moss Portal](https://usemoss.dev) to set up projects and start building with sub-10ms search.
:::

## Common use cases

- **Copilot memory** — Recall user context instantly, even offline
- **Docs search** — Fast, private search inside help centers and knowledge bases
- **Desktop productivity** — Smart search in note apps or IDEs without sending data online
- **AI-native apps** — Sub-10ms search on phones and AI-PCs with no lag even on bad networks

## Quick start

::: code-group

```bash [npm]
npm install @moss-dev/moss-web
```

```bash [pip]
pip install moss
```

:::

::: code-group

```ts [JavaScript]
import { MossClient } from '@moss-dev/moss-web'

const client = new MossClient(process.env.PROJECT_ID!, process.env.PROJECT_KEY!)
await client.createIndex('docs', [{ id: '1', text: 'Vector search in production' }])

await client.loadIndex('docs')
const results = await client.query('docs', 'production search tips')
```

```py [Python]
from moss import MossClient, DocumentInfo

client = MossClient("$PROJECT_ID", "$PROJECT_KEY")
await client.create_index(
    "docs",
    [DocumentInfo(id="1", text="Vector search in production")],
)

await client.load_index("docs")
results = await client.query("docs", "production search tips")
```

:::

## Next steps

| Task | Link |
| --- | --- |
| Project setup and credentials | [Getting Started](/getting-started) |
| JavaScript usage and API docs | [JavaScript SDK](/reference/js/README.md) |
| Python usage and API docs | [Python SDK](/reference/python/README.md) |

## Contact

For support, commercial licensing, or partnership inquiries: [contact@moss.dev](mailto:contact@moss.dev)

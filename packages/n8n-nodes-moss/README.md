# n8n-nodes-moss

n8n community node for [Moss](https://docs.moss.dev) semantic search.

Index documents and run semantic queries from any n8n workflow via the Moss Control Plane HTTP API — no separate vector database or embedding API required.

Implements [usemoss/moss#345](https://github.com/usemoss/moss/issues/345).

## Installation

### Community nodes UI

In self-hosted n8n: **Settings → Community Nodes → Install** → `n8n-nodes-moss`.

### npm (self-hosted n8n)

Install into n8n's community nodes directory, then restart n8n:

```bash
# On the host running n8n
mkdir -p ~/.n8n/nodes
cd ~/.n8n/nodes
npm install n8n-nodes-moss
```

If n8n runs in Docker, run the install inside the container (or a volume mounted at `/home/node/.n8n/nodes`), then restart the container.

Alternatively, in the UI: **Settings → Community Nodes → Install** → `n8n-nodes-moss`.

### From this monorepo

```bash
cd packages/n8n-nodes-moss
npm install --ignore-scripts
npm run build
npm test
```

Then point n8n at the package:

```bash
export N8N_CUSTOM_EXTENSIONS=/absolute/path/to/packages/n8n-nodes-moss
n8n start
```

## Credentials

Create a **Moss API** credential with values from the [Moss Portal](https://portal.usemoss.dev):

| Field | Description |
|---|---|
| Project ID | Your Moss project ID |
| Project Key | Your Moss project access key |

Credential test calls `listIndexes` against `https://service.usemoss.dev/v1/manage`.

## Operations

| Operation | Description |
|---|---|
| **Query** | Semantic search against an index (cloud `/query`) |
| **Create Index** | Create an index from a JSON document array |
| **Add Documents** | Upsert documents into an existing index |
| **Delete Documents** | Remove documents by ID |
| **Get Documents** | Fetch stored documents |
| **List Indexes** | List every index in the project |
| **Get Index** | Fetch index metadata |
| **Delete Index** | Delete an index |
| **Get Job Status** | Poll async create / add / delete jobs |

Mutating operations (**Create Index**, **Add Documents**, **Delete Documents**) support:

- **Wait for Completion** (default: on) — poll until the job finishes
- **Max Wait (Seconds)** (default: 300) — then fail with the `jobId` so you can continue via **Get Job Status**

## Example: Query

1. Add a **Moss** node
2. Select operation **Query**
3. Set **Index Name** and **Query**
4. Optionally set **Top K**

## Example: Create Index

**Documents** field (JSON):

```json
[
  { "id": "faq-1", "text": "We offer a 30-day return policy." },
  { "id": "faq-2", "text": "Track your order from your account dashboard.", "metadata": { "source": "faq" } }
]
```

## Architecture

This node talks to the public Moss HTTP APIs directly (no native SDK bindings):

- Manage: `POST https://service.usemoss.dev/v1/manage`
- Query: `POST https://service.usemoss.dev/query`

Create Index uses the documented upload flow (`initUpload` → binary PUT → `startBuild` → optional poll), with `dimension: 0` so Moss generates embeddings server-side.

## License

BSD 2-Clause — see [LICENSE](LICENSE).

## Support

- [Moss Docs](https://docs.moss.dev)
- [Moss Control Plane API](https://docs.moss.dev/docs/api-reference/v1/getting-started/introduction)
- [Moss Discord](https://discord.gg/eMXExuafBR)

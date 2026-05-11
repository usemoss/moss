# Moss N8N Integration Cookbook

This cookbook provides a TypeScript helper and example workflow for integrating Moss with n8n, the open-source workflow automation platform.

## Overview

The integration exposes Moss's core operations so any n8n workflow can incorporate real-time semantic search without writing SDK code from scratch:

- **Moss: Create Index** - Bootstrap a new index from an upstream data source
- **Moss: Add Documents** - Upsert one or more documents (with optional metadata) into an index
- **Moss: Delete Documents** - Remove documents by ID
- **Moss: Query** - Run a semantic/hybrid search query against an existing index

## Files

1. `moss-n8n-helper.ts` - A TypeScript wrapper around the Moss SDK optimized for n8n usage
2. `n8n-moss-workflow.json` - An example n8n workflow demonstrating the four core operations

## Usage

### Option 1: Using the TypeScript Helper (Recommended)

For the best developer experience, use the provided TypeScript helper in your n8n Function nodes:

1. Copy `moss-n8n-helper.ts` to your n8n custom nodes directory or bundle it with your workflow
2. Import and use it in Function nodes:

```typescript
// Import the helper (adjust path as needed)
import { MossN8NHelper } from './moss-n8n-helper';

// Initialize with your Moss credentials
const helper = new MossN8NHelper('your-project-id', 'your-project-key');

// Create an index
const createResult = await helper.createIndex('my-index', [
  { id: '1', text: 'Hello world', metadata: { source: 'example' } }
]);

// Add documents
await helper.addDocs('my-index', [
  { id: '2', text: 'Another document', metadata: { source: 'example' } }
]);

// Query the index
const results = await helper.query('my-index', 'hello', { topK: 5 });

// Delete documents
await helper.deleteDocs('my-index', ['1']);

// Clean up
helper.dispose();
```

### Option 2: Direct HTTP Requests

If you prefer not to use the helper, you can call Moss's public REST endpoints directly using n8n's HTTP Request nodes. Refer to the [Moss API documentation](https://docs.moss.dev) for endpoint details.

## Example Workflow

The included `n8n-moss-workflow.json` demonstrates a complete workflow:

1. **Start** - Manual trigger to begin the workflow
2. **Moss Config** - Function node to set up Moss credentials
3. **Create Moss Index** - Function node showing how to create an index
4. **Add Documents** - Function node showing how to add documents
5. **Query Moss Index** - Function node showing how to query the index
6. **Delete Documents** - Function node showing how to delete documents

Note: The example workflow uses Function nodes to illustrate the logic. In a real implementation, you would replace the placeholder code with actual calls to the Moss N8N Helper.

## Common Use Cases

### Real-time Knowledge Base Sync
Pair n8n triggers (Google Drive, GitHub, Postgres, etc.) with the Moss "Add Documents" node to automatically keep a semantic index in sync with any upstream source.

### RAG Pipelines Without Code
Feed data from various sources into a Moss index entirely within n8n workflows, then query it from AI agents or LLMs—no custom SDK code required.

### AI Agent Workflows
Use the Moss query operation within AI agent chains to retrieve relevant context before generating responses.

## Requirements

- Node.js >= 16
- n8n >= 0.200.0
- Moss account with project ID and project key

## Setup

1. Obtain your Moss project ID and project key from [Moss Dashboard](https://app.moss.dev)
2. Install the Moss JavaScript SDK in your n8n environment (if using the helper approach):
   ```bash
   npm install @moss-dev/moss
   ```
3. Import the helper into your n8n Function nodes as shown above

## Development

To modify the helper:
1. Edit `moss-n8n-helper.ts`
2. Rebuild if necessary (though TypeScript works directly in n8n Function nodes)
3. Test with your n8n instance

## License

BSD-2-Clause - See [LICENSE](../LICENSE) for details.
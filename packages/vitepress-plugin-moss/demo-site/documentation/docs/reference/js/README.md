---
title: JavaScript SDK
---

**@inferedge/moss v1.0.0-beta.7**

***

# Moss client library for JavaScript

`@inferedge/moss` enables **private, on-device semantic search** in your web, mobile, and edge applications - without cloud dependencies.

Built for developers who want **instant, memory-efficient, privacy-first AI features** inside their apps.

## ✨ Features

- ⚡ **On-Device Vector Search** - Sub-millisecond retrieval with zero network latency
- 🔍 **Semantic Search & Hybrid Search** - Beyond keyword matching
- 📦 **Multi-Index Support** - Manage multiple isolated search spaces
- 🛠️ **Tiny SDK** - Optimized for edge deployments
- 🛡️ **Privacy-First by Design** - No server-side cloud calls required to perform searches

## 📦 Installation

```bash
npm install @inferedge/moss
```

## 🚀 Quick Start

```typescript
import { MossClient, DocumentInfo } from "@inferedge/moss";

async function main() {
  // Initialize search client with project credentials
  const mossClient = new MossClient(
    "your-project-id",
    "your-project-key"
  );

  // Prepare documents to index
  const documents: DocumentInfo[] = [
    {
      id: "doc1",
      text: "How do I track my order? You can track your order by logging into your account.",
    },
    {
      id: "doc2", 
      text: "What is your return policy? We offer a 30-day return policy for most items.",
    },
    {
      id: "doc3",
      text: "How can I change my shipping address? Contact our customer service team.",
    },
    // Add more documents here
    // .
    // .
    // .
  ];

  // Create an index with documents and model
  const indexName = "faqs";
  const created = await mossClient.createIndex(
    indexName,
    documents
  ); // Defaults to the service's `moss-minilm` model when omitted
  console.log("Index created:", created);

  // Load the index before searching
  await mossClient.loadIndex(indexName);

  // Search the index
  const result = await mossClient.query(indexName, "How do I return a damaged product?", {
    topK: 3,
  });

  // Display results
  console.log(`Query: ${result.query}`);
  result.docs.forEach((match) => {
    console.log(`Score: ${match.score.toFixed(4)}`);
    console.log(`ID: ${match.id}`);
    console.log(`Text: ${match.text}`);
    console.log("---");
  });
}

main().catch(console.error);
```

## 🔥 Example Use Cases

- Smart knowledge base search
- Realtime Voice AI agents
- Personal note-taking search
- Private in-app AI features (recommendations, retrieval)
- Local semantic search in edge devices, AR/VR, mobile apps

## 🧠 Providing custom embeddings

Already using your own embedding model? Supply vectors directly when managing indexes:

```typescript
const documents = [
  {
    id: "doc-1",
    text: "Attach a caller-provided embedding",
    embedding: myEmbeddingModel("doc-1"),
  },
  {
    id: "doc-2",
    text: "Fallback to the built-in model when the field is omitted.",
  },
];

await mossClient.createIndex("custom-embeddings", documents);

await mossClient.loadIndex("custom-embeddings");

const results = await mossClient.query("custom-embeddings", "", {
  embedding: myEmbeddingModel("query"),
  topK: 10,
});
```

Leaving `modelId` undefined defaults to `moss-minilm`. You can still pass `{ modelId: "moss-mediumlm" }` or another supported identifier if you want the service to generate embeddings for documents without the optional `embedding` field.

## 📄 License

This package is licensed under the [PolyForm Shield License 1.0.0](_media/LICENSE.txt).

- ✅ Free for testing, evaluation, internal use, and modifications.
- ❌ Not permitted for production or competing commercial use.
- 📩 For commercial licenses, contact: <contact@inferedge.dev>

## 📬 Contact

For support, commercial licensing, or partnership inquiries, contact us: [contact@inferedge.dev](mailto:contact@inferedge.dev)

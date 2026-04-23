/**
 * Seed Script for Moss Bun
 *
 * Populates the index with sample data for demo/testing
 */

import { MossClient } from "@moss-dev/moss";
import { config } from "dotenv";

config();

const MOSS_PROJECT_ID = process.env.MOSS_PROJECT_ID || "";
const MOSS_PROJECT_KEY = process.env.MOSS_PROJECT_KEY || "";

if (!MOSS_PROJECT_ID || !MOSS_PROJECT_KEY) {
  console.error("❌ Error: MOSS_PROJECT_ID and MOSS_PROJECT_KEY are required");
  process.exit(1);
}

const client = new MossClient(MOSS_PROJECT_ID, MOSS_PROJECT_KEY);

// Sample documents about different topics
const SAMPLE_DOCUMENTS = [
  // Moss Documentation
  {
    id: "moss-intro",
    text: "Moss is a semantic search runtime designed for AI agents. It delivers sub-10ms search results with built-in embeddings, making it perfect for real-time conversational applications.",
  },
  {
    id: "moss-features",
    text: "Key features of Moss: sub-10ms latency, built-in embedding models, metadata filtering, document management, and framework integrations with LangChain, DSPy, and Pipecat.",
  },
  {
    id: "moss-performance",
    text: "Moss achieves P50 latency of 3.1ms, P95 of 4.3ms, and P99 of 5.4ms on 100,000 documents. This includes embedding computation, unlike competitors that use external services.",
  },
  {
    id: "moss-sdks",
    text: "Moss provides async-first SDKs for Python and TypeScript. The Python SDK uses asyncio, while the TypeScript SDK is compatible with Node.js, Bun, and Deno.",
  },

  // Bun Information
  {
    id: "bun-runtime",
    text: "Bun is an all-in-one JavaScript/TypeScript runtime that replaces Node.js, npm, and webpack. It executes code 2-3x faster than Node.js with native TypeScript support.",
  },
  {
    id: "bun-features",
    text: "Bun includes built-in HTTP server, package manager, bundler, test runner, and shell scripting. It's compatible with npm packages and provides WebSocket support.",
  },
  {
    id: "bun-ecosystem",
    text: "Bun supports popular frameworks like Next.js, React, Vue, and Express. It can generate standalone executables and has a Jest-compatible test runner.",
  },

  // AI & LLM
  {
    id: "llm-intro",
    text: "Large Language Models (LLMs) are neural networks trained on vast amounts of text data. They can generate human-like text, answer questions, and assist with various NLP tasks.",
  },
  {
    id: "rag-pattern",
    text: "Retrieval-Augmented Generation (RAG) combines semantic search with language models. It retrieves relevant documents first, then uses them as context for generation.",
  },
  {
    id: "embeddings",
    text: "Embeddings are dense vector representations of text. Modern embedding models like BERT and sentence-transformers convert text into semantic vectors for similarity search.",
  },

  // Development
  {
    id: "typescript-benefits",
    text: "TypeScript adds static typing to JavaScript, enabling better IDE support, early error detection, and improved code maintainability for large projects.",
  },
  {
    id: "rest-api",
    text: "REST APIs use HTTP methods (GET, POST, PUT, DELETE) to perform CRUD operations on resources. They're stateless and widely supported across all platforms.",
  },
  {
    id: "docker-containerization",
    text: "Docker containers package applications with dependencies, ensuring consistent execution across development, testing, and production environments.",
  },
];

async function seed() {
  console.log("🌱 Seeding Moss index...\n");

  const indexName = process.argv[2] || "moss-demo";

  try {
    console.log(`📝 Creating index "${indexName}" with ${SAMPLE_DOCUMENTS.length} documents...\n`);

    // Create index with documents
    await client.createIndex(indexName, SAMPLE_DOCUMENTS);

    console.log(`✓ Index created successfully!\n`);

    // Load index
    console.log(`🔄 Loading index for verification...\n`);
    await client.loadIndex(indexName);

    console.log(`✓ Index loaded!\n`);

    // Test a search
    console.log(`🔍 Testing search capability...\n`);

    const testQueries = ["what is moss?", "tell me about bun", "explain embeddings"];

    for (const query of testQueries) {
      const results = await client.query(indexName, query, { topK: 2 });

      console.log(`Query: "${query}"`);
      console.log(`Results (${results.timeTakenInMs}ms):`);

      results.docs.forEach((doc, i) => {
        const preview = doc.text.substring(0, 60) + "...";
        console.log(`  ${i + 1}. [${doc.id}] ${doc.score.toFixed(3)} - ${preview}`);
      });

      console.log();
    }

    console.log(`
                ✅ Seeding Complete!    
 Index Name: ${indexName}
 Documents: ${SAMPLE_DOCUMENTS.length}
 Status: Ready for queries

Now you can:
  • Start the server: bun run src/index.ts
  • Search via CLI: bun run src/cli.ts search "query" ${indexName}
  • Use the API: curl -X POST http://localhost:3000/api/search
`);
  } catch (error) {
    console.error("❌ Error:", error);
    process.exit(1);
  }
}

seed();

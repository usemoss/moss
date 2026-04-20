#!/usr/bin/env bun
/**
 * Moss Bun CLI
 *
 * Command-line interface for Moss semantic search
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

// Parse command line arguments
const command = process.argv[2];
const args = process.argv.slice(3);

async function main() {
  switch (command) {
    case "search": {
      const query = args[0];
      const indexName = args[1] || "default";
      const topK = parseInt(args[2] || "5");

      if (!query) {
        console.error("Usage: bun run cli.ts search <query> [indexName] [topK]");
        process.exit(1);
      }

      try {
        console.log(`Searching "${indexName}" for: "${query}"\n`);

        await client.loadIndex(indexName);
        const results = await client.query(indexName, query, { topK });

        console.log(`Found ${results.docs.length} results in ${results.timeTakenInMs}ms\n`);

        results.docs.forEach((doc, i) => {
          console.log(`${i + 1}. [${doc.id}] Score: ${doc.score.toFixed(3)}`);
          console.log(`   ${doc.text}\n`);
        });
      } catch (error) {
        console.error("❌ Error:", error);
        process.exit(1);
      }
      break;
    }

    case "init": {
      const indexName = args[0];
      const docCount = parseInt(args[1] || "5");

      if (!indexName) {
        console.error("Usage: bun run cli.ts init <indexName> [docCount]");
        process.exit(1);
      }

      try {
        console.log(`📝 Creating index "${indexName}" with ${docCount} sample documents...\n`);

        // Create sample documents
        const documents = Array.from({ length: docCount }, (_, i) => ({
          id: `doc-${i + 1}`,
          text: [
            "Moss is a semantic search runtime for AI agents with sub-10ms latency",
            "Built-in embeddings mean you don't need external APIs or services",
            "Perfect for real-time voice bots, copilots, and conversational AI",
            "Supports Python and TypeScript SDKs with async-first design",
            "Includes metadata filtering with $eq, $and, $in, $near operators",
          ][i % 5],
        }));

        await client.createIndex(indexName, documents);
        console.log(`✓ Index "${indexName}" created successfully`);
        console.log(`  Documents: ${documents.length}`);
        console.log(`  Ready for queries!\n`);
      } catch (error) {
        console.error("❌ Error:", error);
        process.exit(1);
      }
      break;
    }

    case "list": {
      try {
        console.log(`📚 Listing all indexes...\n`);
        const indexes = await client.listIndexes();

        if (indexes.length === 0) {
          console.log("No indexes found");
        } else {
          indexes.forEach((index) => {
            console.log(`• ${index.name}`);
            console.log(`  Created: ${new Date(index.createdAt || "").toLocaleString()}`);
            console.log();
          });
        }
      } catch (error) {
        console.error("❌ Error:", error);
        process.exit(1);
      }
      break;
    }

    case "info": {
      const indexName = args[0];

      if (!indexName) {
        console.error("Usage: bun run cli.ts info <indexName>");
        process.exit(1);
      }

      try {
        console.log(`📊 Index info for "${indexName}":\n`);
        const index = await client.getIndex(indexName);

        console.log(`Name: ${index.name}`);
        console.log(`Created: ${new Date(index.createdAt || "").toLocaleString()}`);
        console.log(`Updated: ${new Date(index.updatedAt || "").toLocaleString()}`);
        console.log();
      } catch (error) {
        console.error("❌ Error:", error);
        process.exit(1);
      }
      break;
    }

    case "delete": {
      const indexName = args[0];

      if (!indexName) {
        console.error("Usage: bun run cli.ts delete <indexName>");
        process.exit(1);
      }

      try {
        console.log(`🗑️  Deleting index "${indexName}"...`);
        await client.deleteIndex(indexName);
        console.log(` Index deleted\n`);
      } catch (error) {
        console.error("❌ Error:", error);
        process.exit(1);
      }
      break;
    }

    case "interactive": {
      const indexName = args[0] || "default";

      try {
        console.log(`\n🌿 Moss Interactive Search`);
        console.log(`📚 Index: ${indexName}\n`);
        console.log(`Type 'quit' to exit\n`);

        await client.loadIndex(indexName);

        const readline = require("readline");
        const rl = readline.createInterface({
          input: process.stdin,
          output: process.stdout,
        });

        const askQuestion = (): void => {
          rl.question("🔍 Search: ", async (query: string) => {
            if (query.toLowerCase() === "quit") {
              console.log("\nGoodbye!");
              rl.close();
              return;
            }

            try {
              const results = await client.query(indexName, query, { topK: 3 });

              console.log(
                `\n✓ Found ${results.docs.length} results in ${results.timeTakenInMs}ms\n`
              );

              results.docs.forEach((doc, i) => {
                console.log(`${i + 1}. [${doc.id}] ${doc.score.toFixed(3)}`);
                console.log(`   ${doc.text}\n`);
              });
            } catch (error) {
              console.error("Error:", error);
            }

            askQuestion();
          });
        };

        askQuestion();
      } catch (error) {
        console.error("❌ Error:", error);
        process.exit(1);
      }
      break;
    }

    default: {
      console.log(`
Moss Bun CLI

Usage: bun run cli.ts <command> [options]

Commands:

  search <query> [indexName] [topK]
    Search for documents
    Example: bun run cli.ts search "what is moss?" my-index 5

  init <indexName> [docCount]
    Create a new index with sample documents
    Example: bun run cli.ts init my-index 10

  list
    List all indexes
    Example: bun run cli.ts list

  info <indexName>
    Get index information
    Example: bun run cli.ts info my-index

  delete <indexName>
    Delete an index
    Example: bun run cli.ts delete my-index

  interactive [indexName]
    Interactive search mode
    Example: bun run cli.ts interactive my-index

Environment Variables:
  MOSS_PROJECT_ID    Your Moss project ID (required)
  MOSS_PROJECT_KEY   Your Moss project key (required)
`);
      process.exit(0);
    }
  }
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});

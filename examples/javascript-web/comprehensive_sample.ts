/**
 * Moss Browser SDK - Comprehensive Sample
 *
 * End-to-end demonstration of every SDK operation:
 *   create index, get info, list indexes, add docs, get docs,
 *   load index, query, delete docs, delete index, dispose.
 */

import { MossClient, type DocumentInfo } from "@moss-dev/moss-web";

const $ = (id: string) => document.getElementById(id) as HTMLInputElement;
const logEl = $("log");
const log = (msg: string) => {
  logEl.textContent += msg + "\n";
};
const clear = () => {
  logEl.textContent = "";
};

$("run").addEventListener("click", run);

const documents: DocumentInfo[] = [
  {
    id: "tech-ai-001",
    text: "Artificial Intelligence (AI) is transforming industries by enabling machines to perform tasks that typically require human intelligence. From healthcare diagnostics to autonomous vehicles, AI applications are revolutionizing how we work and live.",
    metadata: {
      category: "technology",
      subcategory: "artificial_intelligence",
      difficulty: "beginner",
      topic: "ai_overview",
    },
  },
  {
    id: "tech-ml-002",
    text: "Machine Learning is a subset of AI that enables systems to automatically learn and improve from experience without being explicitly programmed. It uses algorithms to analyze data, identify patterns, and make predictions or decisions.",
    metadata: {
      category: "technology",
      subcategory: "machine_learning",
      difficulty: "intermediate",
      topic: "ml_fundamentals",
    },
  },
  {
    id: "tech-dl-003",
    text: "Deep Learning uses artificial neural networks with multiple layers to model and understand complex patterns in data. It has achieved breakthrough results in image recognition, natural language processing, and game playing.",
    metadata: {
      category: "technology",
      subcategory: "deep_learning",
      difficulty: "advanced",
      topic: "neural_networks",
    },
  },
  {
    id: "tech-nlp-004",
    text: "Natural Language Processing (NLP) enables computers to understand, interpret, and generate human language. Applications include chatbots, language translation, sentiment analysis, and text summarization.",
    metadata: {
      category: "technology",
      subcategory: "natural_language_processing",
      difficulty: "intermediate",
      topic: "language_processing",
    },
  },
  {
    id: "tech-cv-005",
    text: "Computer Vision allows machines to interpret and understand visual information from the world. It powers applications like facial recognition, medical image analysis, autonomous driving, and quality control in manufacturing.",
    metadata: {
      category: "technology",
      subcategory: "computer_vision",
      difficulty: "intermediate",
      topic: "visual_recognition",
    },
  },
  {
    id: "business-data-006",
    text: "Data Science combines statistics, programming, and domain expertise to extract actionable insights from data. It involves data collection, cleaning, analysis, and visualization to support business decision-making.",
    metadata: {
      category: "business",
      subcategory: "data_science",
      difficulty: "intermediate",
      topic: "analytics",
    },
  },
  {
    id: "business-cloud-007",
    text: "Cloud Computing provides on-demand access to computing resources over the internet, including servers, storage, databases, and software. It offers scalability, cost-efficiency, and global accessibility for businesses.",
    metadata: {
      category: "business",
      subcategory: "cloud_computing",
      difficulty: "beginner",
      topic: "infrastructure",
    },
  },
];

const additionalDocs: DocumentInfo[] = [
  {
    id: "security-cyber-008",
    text: "Cybersecurity protects digital systems, networks, and data from cyber threats. It involves implementing security measures, monitoring for vulnerabilities, and responding to incidents to maintain data integrity and privacy.",
  },
  {
    id: "health-biotech-009",
    text: "Biotechnology applies biological processes and organisms to develop products and technologies that improve human health and the environment. It includes genetic engineering, drug development, and personalized medicine.",
  },
];

async function run() {
  clear();

  const projectId = $("projectId").value.trim();
  const projectKey = $("projectKey").value.trim();

  if (!projectId || !projectKey) {
    log("Please enter project credentials.");
    return;
  }

  const indexName = `web-demo-${Date.now()}`;
  let client: MossClient | null = null;

  try {
    log("Initializing MossClient...");
    client = new MossClient(projectId, projectKey);

    // 1. Create index
    log(`\n1. Creating index "${indexName}" with ${documents.length} documents...`);
    const created = await client.createIndex(indexName, documents, {
      modelId: "moss-minilm",
    });
    log(`   Created: ${created.indexName} (${created.docCount} docs, job: ${created.jobId})`);

    // 2. Get index info
    log("\n2. Getting index info...");
    const info = await client.getIndex(indexName);
    log(`   Name: ${info.name}`);
    log(`   Docs: ${info.docCount}`);
    log(`   Model: ${info.model.id}`);
    log(`   Status: ${info.status}`);

    // 3. List indexes
    log("\n3. Listing all indexes...");
    const indexes = await client.listIndexes();
    log(`   Found ${indexes.length} indexes:`);
    for (const idx of indexes) {
      log(`   - ${idx.name} (${idx.docCount} docs, ${idx.status})`);
    }

    // 4. Add documents
    log(`\n4. Adding ${additionalDocs.length} documents with upsert...`);
    const added = await client.addDocs(indexName, additionalDocs, {
      upsert: true,
    });
    log(`   Added: ${added.docCount} docs (job: ${added.jobId})`);

    // 5. Get all documents
    log("\n5. Retrieving all documents...");
    const allDocs = await client.getDocs(indexName);
    log(`   Total documents: ${allDocs.length}`);
    for (const doc of allDocs.slice(0, 3)) {
      const preview =
        doc.text.length > 70 ? doc.text.slice(0, 70) + "..." : doc.text;
      log(`   - [${doc.id}] ${preview}`);
    }
    if (allDocs.length > 3) log(`   ... and ${allDocs.length - 3} more`);

    // 6. Get specific documents
    log("\n6. Retrieving specific documents by ID...");
    const targetIds = ["tech-ai-001", "business-data-006", "security-cyber-008"];
    const specific = await client.getDocs(indexName, { docIds: targetIds });
    log(`   Retrieved ${specific.length} of ${targetIds.length} requested:`);
    for (const doc of specific) {
      const preview = doc.text.length > 60 ? doc.text.slice(0, 60) + "..." : doc.text;
      log(`   - [${doc.id}] ${preview}`);
    }

    // 7. Load index for querying
    log("\n7. Loading index into browser memory...");
    await client.loadIndex(indexName);
    log("   Index loaded.");

    // 8. Semantic search
    log("\n8. Running semantic searches...");
    const searches = [
      { query: "artificial intelligence and machine learning", topK: 3 },
      { query: "data analysis and business insights", topK: 3 },
      { query: "cybersecurity and data protection", topK: 2 },
    ];

    for (const { query, topK } of searches) {
      log(`\n   "${query}"`);
      const results = await client.query(indexName, query, { topK });
      log(`   ${results.docs.length} results in ${results.timeTakenMs ?? "?"}ms:`);
      for (const doc of results.docs) {
        log(`   ${doc.score.toFixed(3)}  [${doc.id}] ${doc.text.slice(0, 70)}...`);
      }
    }

    // 9. Delete documents
    log("\n9. Deleting 2 documents...");
    const docsToDelete = ["health-biotech-009", "security-cyber-008"];
    const deleted = await client.deleteDocs(indexName, docsToDelete);
    log(`   Deleted (job: ${deleted.jobId}, remaining: ${deleted.docCount})`);

    // 10. Verify
    log("\n10. Verifying document count...");
    const remaining = await client.getDocs(indexName);
    log(`    Remaining documents: ${remaining.length}`);

    // 11. Cleanup
    log("\n11. Deleting test index...");
    const didDelete = await client.deleteIndex(indexName);
    log(`    Index deleted: ${didDelete}`);

    log("\nAll steps completed successfully.");
  } catch (err) {
    log(`\nError: ${err instanceof Error ? err.message : err}`);

    try {
      await client?.deleteIndex(indexName);
      log("Cleanup: test index deleted.");
    } catch {
      log("Cleanup: could not delete test index (may not exist).");
    }
  } finally {
    client?.dispose();
  }
}

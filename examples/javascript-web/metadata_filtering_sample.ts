/**
 * Moss Browser SDK - Metadata Filtering Sample
 *
 * Creates an index with metadata-rich documents, then demonstrates
 * $eq, $and, $or, $lt, $in, and $near filters on queries.
 */

import {
  MossClient,
  type DocumentInfo,
  type MetadataFilter,
} from "@moss-dev/moss-web";

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
    id: "doc1",
    text: "Running shoes with breathable mesh for daily training.",
    metadata: {
      category: "shoes",
      brand: "swiftfit",
      price: "79",
      city: "new-york",
      location: "40.7580,-73.9855",
    },
  },
  {
    id: "doc2",
    text: "Trail running shoes built for rocky mountain terrain.",
    metadata: {
      category: "shoes",
      brand: "peakstride",
      price: "149",
      city: "seattle",
      location: "47.6062,-122.3321",
    },
  },
  {
    id: "doc3",
    text: "Lightweight city backpack with laptop compartment.",
    metadata: {
      category: "bags",
      brand: "urbanpack",
      price: "95",
      city: "new-york",
      location: "40.7505,-73.9934",
    },
  },
  {
    id: "doc4",
    text: "Waterproof hiking boots with ankle support for all-day treks.",
    metadata: {
      category: "shoes",
      brand: "peakstride",
      price: "189",
      city: "denver",
      location: "39.7392,-104.9903",
    },
  },
  {
    id: "doc5",
    text: "Compact travel duffel bag with shoe compartment.",
    metadata: {
      category: "bags",
      brand: "swiftfit",
      price: "65",
      city: "seattle",
      location: "47.6205,-122.3493",
    },
  },
];

async function runFilteredQuery(
  client: MossClient,
  indexName: string,
  label: string,
  query: string,
  filter: MetadataFilter
) {
  log(`\n${label}`);
  log(`  query: "${query}"`);
  log(`  filter: ${JSON.stringify(filter)}`);

  const results = await client.query(indexName, query, {
    topK: 5,
    alpha: 0.5,
    filter,
  });

  if (results.docs.length === 0) {
    log("  (no results)");
  }
  for (const doc of results.docs) {
    const preview = doc.text.length > 70 ? doc.text.slice(0, 70) + "..." : doc.text;
    log(`  - ${doc.id} | score=${doc.score.toFixed(3)} | ${preview}`);
  }
}

async function run() {
  clear();

  const projectId = $("projectId").value.trim();
  const projectKey = $("projectKey").value.trim();

  if (!projectId || !projectKey) {
    log("Please enter project credentials.");
    return;
  }

  const indexName = `filter-demo-${Date.now()}`;
  let client: MossClient | null = null;

  try {
    log("Initializing MossClient...");
    client = new MossClient(projectId, projectKey);

    log(`\n1. Creating index "${indexName}" with ${documents.length} documents...`);
    await client.createIndex(indexName, documents);

    log("2. Loading index into browser memory...");
    await client.loadIndex(indexName);
    log("   Index loaded.\n");

    // $eq - exact match
    await runFilteredQuery(client, indexName, "3. $eq filter: category == shoes", "running gear", {
      field: "category",
      condition: { $eq: "shoes" },
    });

    // $and - combine conditions
    await runFilteredQuery(
      client,
      indexName,
      "4. $and filter: shoes AND price < 100",
      "affordable running shoes",
      {
        $and: [
          { field: "category", condition: { $eq: "shoes" } },
          { field: "price", condition: { $lt: "100" } },
        ],
      }
    );

    // $in - match any value in list
    await runFilteredQuery(
      client,
      indexName,
      "5. $in filter: city in [new-york, denver]",
      "outdoor gear",
      {
        field: "city",
        condition: { $in: ["new-york", "denver"] },
      }
    );

    // $or - either condition
    await runFilteredQuery(
      client,
      indexName,
      "6. $or filter: brand is swiftfit OR brand is urbanpack",
      "travel essentials",
      {
        $or: [
          { field: "brand", condition: { $eq: "swiftfit" } },
          { field: "brand", condition: { $eq: "urbanpack" } },
        ],
      }
    );

    // $near - geo proximity (within 5 km of Times Square)
    await runFilteredQuery(
      client,
      indexName,
      "7. $near filter: within 5 km of Times Square (40.7580, -73.9855)",
      "city products",
      {
        field: "location",
        condition: { $near: "40.7580,-73.9855,5000" },
      }
    );

    log("\nMetadata filtering sample completed.");

    // Cleanup
    log("\n8. Deleting test index...");
    await client.deleteIndex(indexName);
    log("   Done.");
  } catch (err) {
    log(`\nError: ${err instanceof Error ? err.message : err}`);

    try {
      await client?.deleteIndex(indexName);
    } catch {
      // ignore cleanup errors
    }
  } finally {
    client?.dispose();
  }
}

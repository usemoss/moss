import { beforeAll, afterAll, describe, it, expect } from "vitest";
import dotenv from "dotenv";

import { MossClient } from "../src";
import {
	TEST_PROJECT_ID,
	TEST_PROJECT_KEY,
	generateUniqueIndexName,
	HAS_REAL_CLOUD_CREDS,
} from "./constants";

dotenv.config();

const CUSTOM_INDEX_NAME = generateUniqueIndexName("test-custom-embeddings");

// Dummy 4-dimensional embeddings — doc-1's vector is closest to the query vector
const DOCUMENTS = [
	{
		id: "custom-doc-1",
		text: "High signal paragraph about custom embeddings.",
		embedding: [0.9, 0.1, 0.05, 0.0],
	},
	{
		id: "custom-doc-2",
		text: "A generic note about unrelated topics to test ranking.",
		embedding: [0.0, 0.1, 0.8, 0.7],
	},
	{
		id: "custom-doc-3",
		text: "Another document discussing embeddings and similarity search.",
		embedding: [0.5, 0.3, 0.1, 0.0],
	},
];
const QUERY_EMBEDDING = [0.95, 0.1, 0.0, 0.0];
const TARGET_DOCUMENT_ID = DOCUMENTS[0]!.id;

describe.skipIf(!HAS_REAL_CLOUD_CREDS)("Custom embeddings end-to-end", () => {
	let client: MossClient;

	beforeAll(async () => {
		client = new MossClient(TEST_PROJECT_ID, TEST_PROJECT_KEY);

		// Ensure the test index does not exist
		try {
			await client.deleteIndex(CUSTOM_INDEX_NAME);
		} catch {
			// Index may not exist; ignore cleanup errors during setup
		}
	});

	afterAll(async () => {
		try {
			await client.deleteIndex(CUSTOM_INDEX_NAME);
		} catch {
			// Ignore cleanup errors
		}
	});

	it("indexes documents with custom embeddings and queries using external vectors", async () => {
		await client.createIndex(CUSTOM_INDEX_NAME, DOCUMENTS);

		await client.loadIndex(CUSTOM_INDEX_NAME);

		const results = await client.query(CUSTOM_INDEX_NAME, "", {
			embedding: QUERY_EMBEDDING,
			topK: DOCUMENTS.length,
		});

		expect(results.docs.length).toBeGreaterThan(0);
		expect(results.docs[0]?.id).toBe(TARGET_DOCUMENT_ID);
		expect(results.docs[0]?.score).toBeGreaterThan(0);
		expect(results.docs.map((doc) => doc.id)).toContain(TARGET_DOCUMENT_ID);
	});
});

/**
 * Test constants for cloud API integration tests
 * Uses dotenv package to load environment variables from .env file
 */

import dotenv from "dotenv";
import { randomUUID } from "crypto";

// Load environment variables from .env file
dotenv.config();

/**
 * Generate a unique index name using UUID to avoid conflicts between test runs.
 * @param prefix - Optional prefix for the index name (default: "test-e2e")
 * @returns A unique index name string
 */
export function generateUniqueIndexName(prefix: string = "test-e2e"): string {
  return `${prefix}-${randomUUID().slice(0, 12)}`;
}

export const TEST_PROJECT_ID =
  process.env.MOSS_TEST_PROJECT_ID || "test-project-id";
export const TEST_PROJECT_KEY =
  process.env.MOSS_TEST_PROJECT_KEY || "test-project-key";

/** True when real cloud credentials are configured via env vars */
export const HAS_REAL_CLOUD_CREDS =
  !!process.env.MOSS_TEST_PROJECT_ID && !!process.env.MOSS_TEST_PROJECT_KEY;

// Test data
export const TEST_INDEX_NAME = `test-e2e-index-${Date.now()}`;
export const TEST_MODEL_ID = "moss-minilm";
export const TEST_IMAGE_INDEX_NAME = "test-e2e-image-index";

export const TEST_DOCUMENTS = [
  {
    id: "doc-1",
    text: "Machine learning is a subset of artificial intelligence that enables computers to learn and improve from experience without being explicitly programmed.",
  },
  {
    id: "doc-2",
    text: "Natural language processing (NLP) is a branch of AI that helps computers understand, interpret and manipulate human language.",
  },
  {
    id: "doc-3",
    text: "Deep learning uses neural networks with multiple layers to model and understand complex patterns in data.",
  },
  {
    id: "doc-4",
    text: "Computer vision enables machines to interpret and understand visual information from the world around them.",
  },
  {
    id: "doc-5",
    text: "Reinforcement learning is a type of machine learning where an agent learns to make decisions by performing actions and receiving rewards.",
  },
];

export const ADDITIONAL_TEST_DOCUMENTS = [
  {
    id: "doc-6",
    text: "Data science combines statistics, programming, and domain expertise to extract insights from data.",
  },
  {
    id: "doc-7",
    text: "Cloud computing provides on-demand access to computing resources over the internet.",
  },
];

// Test queries for semantic search
export const TEST_QUERIES = [
  {
    query: "AI and neural networks",
    expectedRelevantDocs: ["doc-1", "doc-2", "doc-3"],
  },
  {
    query: "learning from rewards",
    expectedRelevantDocs: ["doc-5"],
  },
  {
    query: "visual understanding",
    expectedRelevantDocs: ["doc-4"],
  },
];

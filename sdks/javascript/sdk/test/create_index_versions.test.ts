import { MossClient, DocumentInfo } from '@moss-dev/moss';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath, pathToFileURL } from 'url';
import { createRequire } from 'module';
import { performance } from 'perf_hooks';
import { TEST_PROJECT_ID, TEST_PROJECT_KEY, TEST_MODEL_ID, HAS_REAL_CLOUD_CREDS } from './constants';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Define the structure of a benchmark result row
type Row = {
  sdkVersion: string;
  docs: number;
  timeMs: number | null;
  ok: boolean;
  note: string;
};

// Function to read the SDK version from package.json
function readSdkVersion(): string {
  const directPath = path.resolve(process.cwd(), 'node_modules/@moss-dev/moss/package.json');

  // First, try to read directly from the expected location
  try {
    if (fs.existsSync(directPath)) {
      const raw = fs.readFileSync(directPath, 'utf-8');
      const parsed = JSON.parse(raw) as { version?: string };
      return parsed.version ?? 'unknown';
    }
  } catch {
    // fall through
  }

  // Fallback: traverse upwards from the module entry point
  try {
    const require = createRequire(import.meta.url);
    const entryPath = require.resolve('@moss-dev/moss');
    let dir = path.dirname(entryPath);
    for (let i = 0; i < 10; i++) {
      const candidate = path.join(dir, 'package.json');
      if (fs.existsSync(candidate)) {
        const raw = fs.readFileSync(candidate, 'utf-8');
        const parsed = JSON.parse(raw) as { version?: string };
        return parsed.version ?? 'unknown';
      }
      const parent = path.dirname(dir);
      if (parent === dir) break;
      dir = parent;
    }

    const pkgPath = require.resolve('@moss-dev/moss/package.json');
    const raw = fs.readFileSync(pkgPath, 'utf-8');
    const parsed = JSON.parse(raw) as { version?: string };
    return parsed.version ?? 'unknown';
  } catch {
    return 'unknown';
  }
}

// Simple deterministic PRNG (Mulberry32), produces a sequence of random numbers based on a given seed.
function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Generates a pseudo-random string using the supplied RNG.
function randomText(len: number, rng: () => number): string {
  const alphabet = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ     ';
  let out = '';
  for (let i = 0; i < len; i++) {
    out += alphabet[Math.floor(rng() * alphabet.length)];
  }
  return out.trim();
}

// Creates deterministic dummy documents
function genDocs(count: number, seed = 1337): DocumentInfo[] {
  const rng = mulberry32(seed);
  const docs: DocumentInfo[] = [];
  for (let i = 0; i < count; i++) {
    docs.push({
      id: `doc_${i}`,
      text: `Document ${i}. ${randomText(200, rng)}`,
      metadata: {},
    });
  }
  return docs;
}

// Classifies errors into categories for reporting
function classifyError(err: unknown): string {
  const msg = err instanceof Error ? err.message : String(err);
  const lower = msg.toLowerCase();
  if (lower.includes('readtimeout') || lower.includes('timeout')) return 'timeout';
  if (msg.includes('status: 413') || lower.includes('payload too large') || msg.includes(' 413 ')) {
    return 'not supported (413/payload too large)';
  }
  if (msg.includes('status: 400') || msg.includes(' 400 ')) return 'HTTP 400';
  if (msg.includes('status: 500') || msg.includes(' 500 ')) return 'HTTP 500';
  if (msg.includes('Cloud API request failed')) return 'Cloud API request failed';
  return msg.length > 120 ? msg.slice(0, 117) + '...' : msg;
}

// Attempts to delete an index, ignoring any errors
async function tryDeleteIndex(client: MossClient, name: string): Promise<void> {
  try {
    await client.deleteIndex(name);
  } catch {
    // ignore
  }
}

// Runs a single benchmark iteration
async function runOnce(client: MossClient, sdkVersion: string, docsCount: number): Promise<Row> {
  const indexName = `createindex-bench-${sdkVersion.replaceAll('.', '_').replaceAll('-', '_')}-${docsCount}`;
  const docs = genDocs(docsCount);

  await tryDeleteIndex(client, indexName);

  const t0 = performance.now();
  try {
    const ok = await client.createIndex(indexName, docs, { modelId: TEST_MODEL_ID });
    const t1 = performance.now();
    await tryDeleteIndex(client, indexName);
    return { sdkVersion, docs: docsCount, timeMs: t1 - t0, ok: Boolean(ok), note: '' };
  } catch (e) {
    const t1 = performance.now();
    await tryDeleteIndex(client, indexName);
    return { sdkVersion, docs: docsCount, timeMs: t1 - t0, ok: false, note: classifyError(e) };
  }
}

// Formats milliseconds for display
function fmtMs(ms: number | null): string {
  if (ms === null) return 'N/A';
  if (ms < 100) return `${ms.toFixed(2)} ms`;
  return `${ms.toFixed(1)} ms`;
}

// Main function to run the benchmark
async function main() {
  const sdkVersion = readSdkVersion();
  const docCounts = [500, 1000, 5000, 8000, 10000, 20000];

  const client = new MossClient(TEST_PROJECT_ID, TEST_PROJECT_KEY);

  const rows: Row[] = [];
  for (let i = 0; i < docCounts.length; i++) {
    const n = docCounts[i];
    process.stdout.write(`Running experiment ${i + 1}/${docCounts.length}: createIndex with ${n} docs... `);
    const row = await runOnce(client, sdkVersion, n);
    rows.push(row);
    process.stdout.write(row.ok ? `✅ ${fmtMs(row.timeMs)}\n` : `❌ failed\n`);
  }

  // Print the results table
  console.log('\n' + '='.repeat(110));
  console.log(' CREATE_INDEX BENCHMARK (TS)');
  console.log('='.repeat(110));
  console.log(`${'sdk_version'.padEnd(16)} | ${'docs'.padStart(6)} | ${'time_taken'.padStart(14)} | ${'status'.padEnd(15)} | notes`);
  console.log('-'.repeat(110));
  for (const r of rows) {
    const status = r.ok ? '✅ success' : '❌ failed';
    console.log(
      `${r.sdkVersion.padEnd(16)} | ${String(r.docs).padStart(6)} | ${fmtMs(r.timeMs).padStart(14)} | ${status.padEnd(15)} | ${r.note}`
    );
  }
  console.log('='.repeat(110) + '\n');
}

const isDirectRun = Boolean(process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href);
if (isDirectRun) {
  main().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}


import { MossClient, DocumentInfo, SearchResult } from '@moss-dev/moss';
import * as fs from 'fs';
import * as readline from 'readline';
import * as path from 'path';
import { fileURLToPath, pathToFileURL } from 'url';
import { TEST_PROJECT_ID, TEST_PROJECT_KEY } from './constants';

// ------------------- Configuration & Imports -------------------

// Load environment variables early so configuration is available in main()

const EMBEDDING_MODEL = "moss-minilm";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Interface for Experiment Configuration
interface ExperimentConfig {
    name: string;
    datasetPath: string;
    alpha: number | null;
    topK: number;
}

// Interface for Run Statistics
interface RunStats {
    experiment: string;
    sdkVersion: string;
    datasetName: string;
    numQueries: number;
    hitRate: number | null;
    mrr: number | null;
    ndcg: number | null;
    avgLatencyMs: number | null;
    p95LatencyMs: number | null;
    errorReason?: string | null;
}

// Dataclass for Caching the dataset to avoid re-loading
class DatasetCache {
    datasetPath: string | null = null;
    qrels: Record<string, Record<string, number>> | null = null;
    queries: Record<string, string> | null = null;
}

// -------------------- Math Helper--------------------

// Calculate mean
function mean(numbers: number[]): number {
    if (numbers.length === 0) return 0;
    return numbers.reduce((a, b) => a + b, 0) / numbers.length;
}

// Calculate quantile
function quantile(numbers: number[], q: number): number {
    if (numbers.length < 2) return numbers[0] ?? 0;
    const sorted = [...numbers].sort((a, b) => a - b);
    const pos = (sorted.length + 1) * q;
    const base = Math.min(sorted.length - 1, Math.max(0, Math.floor(pos) - 1));
    const rest = pos - (base + 1);
    const next = sorted[base + 1] ?? sorted[base];
    return sorted[base] + rest * (next - sorted[base]);
}

// NDCG Calculation
// NDCG (Normalized Discounted Cumulative Gain) measures ranking quality by considering
// both relevance and position. Higher positions and higher relevance scores contribute more.
// 
// Formula: NDCG@k = DCG@k / IDCG@k
// - DCG@k = Σ(i=0 to k-1) (2^rel_i - 1) / log2(i + 2)
//   * Sums relevance gains (2^rel - 1) discounted by position (log2(i+2))
// - IDCG@k = DCG of the ideal ranking (documents sorted by relevance descending)
// - Result: Score between 0.0 (worst) and 1.0 (perfect ranking)
function calculate_ndcg(retrievedIds: string[], trueRels: Record<string, number>, k: number): number {
    let dcg = 0.0;
    let idcg = 0.0;

    // 1. DCG
    for (let i = 0; i < Math.min(retrievedIds.length, k); i++) {
        const docId = retrievedIds[i];
        const rel = trueRels[docId] || 0;
        if (rel > 0) {
            dcg += (Math.pow(2, rel) - 1) / Math.log2(i + 2);
        }
    }

    // 2. IDCG (Ideal ordering)
    const idealScores = Object.values(trueRels).sort((a, b) => b - a).slice(0, k);
    for (let i = 0; i < idealScores.length; i++) {
        const rel = idealScores[i];
        idcg += (Math.pow(2, rel) - 1) / Math.log2(i + 2);
    }

    return idcg > 0 ? dcg / idcg : 0.0;
}

// -------------------- Data Loaders --------------------

// Loads the corpus from the corpus.jsonl file and combines the title and text into a single string
async function load_corpus(filePath: string): Promise<DocumentInfo[]> {
    if (!fs.existsSync(filePath)) {
        console.error(`❌ File not found: ${filePath}`);
        process.exit(1);
    }

    console.log(`Loading docs from ${path.basename(filePath)}...`);
    const docs: DocumentInfo[] = [];
    
    const fileStream = fs.createReadStream(filePath);
    const rl = readline.createInterface({
        input: fileStream,
        crlfDelay: Infinity
    });

    for await (const line of rl) {
        if (!line.trim()) continue;
        try {
            const data = JSON.parse(line);
            // Combine title + text for best search results
            const text = ((data.title || "") + " " + (data.text || "")).trim();
            docs.push({
                id: String(data._id),
                text: text,
                metadata: {}
            });
        } catch (e) {
            // ignore parse errors for empty lines
        }
    }

    console.log(`   Loaded ${docs.length} documents.`);
    return docs;
}

//-------- Loads the qrels from the qrels/test.tsv file --------
// Example struct of qrels : {"query-id": {"doc-id": score}}
function load_qrels(filePath: string): Record<string, Record<string, number>> {
    if (!fs.existsSync(filePath)) {
        console.error(`❌ Qrels file not found: ${filePath}`);
        process.exit(1);
    }

    // Define cache path
    const cachePath = path.join(path.dirname(filePath), path.basename(filePath, path.extname(filePath)) + "_cache.json");

    // Check if cache exists and is newer than source file
    if (fs.existsSync(cachePath)) {
        const cacheStat = fs.statSync(cachePath);
        const sourceStat = fs.statSync(filePath);
        
        // Load from cache
        if (cacheStat.mtime >= sourceStat.mtime) {
            console.log(`Loading qrels from cache: ${path.basename(cachePath)}...`);
            const cachedContent = fs.readFileSync(cachePath, 'utf-8');
            const qrels = JSON.parse(cachedContent);
            console.log(`   Loaded ${Object.keys(qrels).length} query judgments from cache.`);
            return qrels;
        }
    }

    // Parse from source file
    console.log(`Loading qrels from ${path.basename(filePath)}...`);
    const qrels: Record<string, Record<string, number>> = {};
    const content = fs.readFileSync(filePath, 'utf-8');
    const lines = content.split('\n');

    for (const line of lines) {
        if (!line.trim()) continue;
        // check/skip header
        if (line.toLowerCase().includes("query-id") && line.toLowerCase().includes("doc-id")) continue;

        const parts = line.trim().split(/\s+/);
        if (parts.length >= 3) {
            const qid = parts[0];
            const did = parts[1];
            const score = parseFloat(parts[2]);

            if (!qrels[qid]) qrels[qid] = {};
            qrels[qid][did] = score;
        }
    }

    // Save to cache
    console.log(`   Caching qrels to ${path.basename(cachePath)}...`);
    fs.writeFileSync(cachePath, JSON.stringify(qrels, null, 2), 'utf-8');
    console.log(`   Loaded ${Object.keys(qrels).length} query judgments.`);
    return qrels;
}
//-------- Loads the queries from the queries.jsonl --------
// Example struct of queries : {"_id": "text"}
async function load_queries(filePath: string, validQids: Set<string>): Promise<Record<string, string>> {
    const queries: Record<string, string> = {};
    
    const fileStream = fs.createReadStream(filePath);
    const rl = readline.createInterface({
        input: fileStream,
        crlfDelay: Infinity
    });

    for await (const line of rl) {
        if (!line.trim()) continue;
        try {
            const data = JSON.parse(line);
            const qid = String(data._id);
            if (validQids.has(qid)) {
                queries[qid] = String(data.text);
            }
        } catch (e) {
            // ignore
        }
    }
    return queries;
}

// -------------------- Core Execution --------------------
// Run a single experiment scenario, based on the provided config
async function run_scenario(
    client: MossClient, 
    config: ExperimentConfig, 
    queries: Record<string, string>, 
    qrels: Record<string, Record<string, number>>, 
    indexName: string,
    sdkVersion: string
): Promise<RunStats> {
    
    console.log(`\nRunning Experiment: ${config.name} (alpha=${config.alpha}, dataset=${path.basename(config.datasetPath)}) \n`);

    const latencies: number[] = [];
    let hits = 0;
    let mrrSum = 0.0;
    let ndcgSum = 0.0;

    const queryEntries = Object.entries(queries);

    for (const [qid, text] of queryEntries) {
        // 1. Search
        let res: SearchResult;
        if (config.alpha === null) {
            res = await client.query(indexName, text, { topK: config.topK });
        } else {
            res = await client.query(indexName, text, { topK: config.topK, alpha: config.alpha ?? undefined });
        }

        // 2. Latency Measurement 
        if (res.timeTakenInMs !== undefined) {
            latencies.push(res.timeTakenInMs);
        }

        // 3. Score
        const retrievedIds = res.docs.map((d: any) => d.id);
        const relevantDocs = qrels[qid] || {};

        // Check Hit & MRR
        let isHit = false;
        for (let rank = 0; rank < retrievedIds.length; rank++) {
            const docId = retrievedIds[rank];
            if (docId in relevantDocs) {
                if (!isHit) {
                    hits++;
                    mrrSum += 1.0 / (rank + 1);
                    isHit = true;
                }
            }
        }

        // Check NDCG
        ndcgSum += calculate_ndcg(retrievedIds, relevantDocs, config.topK);
    }

    const count = queryEntries.length;

    return {
        experiment: config.name,
        sdkVersion,
        datasetName: path.basename(config.datasetPath),
        numQueries: count,
        hitRate: count > 0 ? hits / count : 0,
        mrr: count > 0 ? mrrSum / count : 0,
        ndcg: count > 0 ? ndcgSum / count : 0,
        avgLatencyMs: latencies.length > 0 ? mean(latencies) : 0,
        p95LatencyMs: latencies.length > 0 ? quantile(latencies, 0.95) : 0
    };
}

// --- 5. MAIN ---

function readSdkVersion(): string {
    // In this repo, this script is typically run from the SDK package itself
    // (e.g. `sdks/javascript/sdk/`), so the most reliable source is the
    // local package.json.
    try {
        const raw = fs.readFileSync(path.resolve(process.cwd(), 'package.json'), 'utf-8');
        const parsed = JSON.parse(raw) as { name?: string; version?: string };
        if (parsed.name === '@moss-dev/moss') {
            return parsed.version ?? "unknown";
        }
    } catch {
        // fall through
    }

    // Minimal fallback for running from other repo subfolders: look for the
    // SDK package.json by walking up.
    let dir = process.cwd();
    for (let i = 0; i < 8; i++) {
        const candidate = path.join(dir, 'sdks/javascript/sdk/package.json');
        if (fs.existsSync(candidate)) {
            try {
                const raw = fs.readFileSync(candidate, 'utf-8');
                const parsed = JSON.parse(raw) as { name?: string; version?: string };
                if (parsed.name === '@moss-dev/moss') {
                    return parsed.version ?? "unknown";
                }
            } catch {
                return "unknown";
            }
        }
        const parent = path.dirname(dir);
        if (parent === dir) break;
        dir = parent;
    }

    return "unknown";
}

// replaces dots and dashes in version string with underscores for safe usage in index names
function safeVersionTag(version: string): string {
    return version.replaceAll(".", "_").replaceAll("-", "_");
}

function classifyIndexCreationError(error: unknown): string | null {
    const msg = error instanceof Error ? error.message : String(error);
    // CloudApiClient wraps errors as: "Cloud API request failed: HTTP error! status: XYZ"
    if (msg.includes("Cloud API request failed")) {
        return "Cloud API request failed";
    }
    if (msg.includes("status: 400")) {
        return "Cloud API rejected dataset error(400): payload failed validation or field limits";
    }
    if (msg.includes("status: 413")) {
        return "Cloud API rejected dataset error(413): payload size exceeds server maximum";
    }
    if (msg.includes("status: 500")) {
        return "Cloud API server error(500): internal server error during index creation";
    }
    return null;
}

async function main() {
    console.log("\n==========================================");
    console.log(" MOSS BENCHMARK: Multi-Dataset Testing (TS)");
    console.log("==========================================\n");

    const projectId = TEST_PROJECT_ID;
    const projectKey = TEST_PROJECT_KEY;

    console.log("Project ID:", projectId);
    console.log("Project Key:", projectKey);

    const client = new MossClient(projectId, projectKey);

    // Resolve base dataset path.
    // In CI we may copy this file into a neutral folder (outside package scope),
    // so prefer an explicit env var or the repo root cwd.
    const envDatasetPath = process.env.MOSS_BENCH_DATASET_PATH;
    const cwdDatasetPath = path.resolve(process.cwd(), 'test-dataset');
    const scriptRelativeDatasetPath = path.resolve(__dirname, '../../../test-dataset');
    const BASE_DATASET_PATH =
        (envDatasetPath && envDatasetPath.trim()) ||
        (fs.existsSync(cwdDatasetPath) ? cwdDatasetPath : scriptRelativeDatasetPath);

    // ---------------------------------------------------------
    // PHASE 1: INDEX PREPARATION (Delete -> Create)
    // ---------------------------------------------------------

    // 1. Define Experiments
    let experiments: ExperimentConfig[] = [
        { name: "Semantic Search(alpha=None)", datasetPath: path.join(BASE_DATASET_PATH, "full_scifact"), alpha: null, topK: 10 },
        { name: "Semantic Search(alpha=None)", datasetPath: path.join(BASE_DATASET_PATH, "full_nfcorpus"), alpha: null, topK: 10 },
        { name: "Semantic Search(alpha=None)", datasetPath: path.join(BASE_DATASET_PATH, "mini_msmarco"), alpha: null, topK: 10 },

        // { name: "Fusion Search(alpha=0.2)", datasetPath: path.join(BASE_DATASET_PATH, "full_scifact"), alpha: 0.2, topK: 10 },
        // ... (other experiments commented out as per original script)
    ];

    // 2. Sort experiments
    experiments = experiments.sort((a, b) => a.datasetPath.localeCompare(b.datasetPath));

    const sdkVersion = readSdkVersion();
    const safeVersion = safeVersionTag(sdkVersion);

    const uniqueDatasetPaths = Array.from(new Set(experiments.map(e => e.datasetPath))).sort((a, b) => a.localeCompare(b));
    const datasetToIndexMap = new Map<string, string>();
    const failedDatasets = new Map<string, { reason: string; indexName: string }>();

    console.log(`\n🚀 PRE-COMPUTING INDICES for ${uniqueDatasetPaths.length} unique datasets...`);

    for (const datasetPath of uniqueDatasetPaths) {
        const datasetName = path.basename(datasetPath);
        const corpusPath = path.join(datasetPath, "corpus.jsonl");

        if (!fs.existsSync(corpusPath)) {
            console.log(`❌ Skipping index creation: Missing corpus at ${datasetName}`);
            continue;
        }

        const indexName = `${datasetName}_${safeVersion}_index`;

        console.log(`\nProcessing ${datasetName}...`);
        const docs = await load_corpus(corpusPath);

        console.log(`   🗑️  Cleaning old index: ${indexName}...`);
        try {
            await client.deleteIndex(indexName);
        } catch {
        }

        console.log(`   ✨ Creating fresh index: ${indexName}...`);
        const t0 = performance.now();
        try {
            const success = await client.createIndex(indexName, docs, { modelId: EMBEDDING_MODEL });
            if (!success) {
                console.log(`   ❌ Failed to create index for ${datasetName}`);
                continue;
            }
            datasetToIndexMap.set(datasetPath, indexName);
            console.log(`   ✅ Created in ${((performance.now() - t0) / 1000).toFixed(2)}s`);
        } catch (error) {
            const reason = classifyIndexCreationError(error);
            if (reason) {
                failedDatasets.set(datasetPath, { reason, indexName });
                console.log(`   ⚠️  ${reason}`);
                continue;
            }
            throw error;
        }
    }

    // ---------------------------------------------------------
    // PHASE 2: EXPERIMENT EXECUTION (Load -> Query)
    // ---------------------------------------------------------

    const results: RunStats[] = [];
    const datasetCache = new DatasetCache();

    for (const exp of experiments) {
        const datasetPath = exp.datasetPath;

        // If dataset failed during preparation, record failure for this experiment and continue
        if (failedDatasets.has(datasetPath)) {
            const failure = failedDatasets.get(datasetPath)!;
            results.push({
                experiment: exp.name,
                sdkVersion,
                datasetName: path.basename(datasetPath),
                numQueries: 0,
                hitRate: null,
                mrr: null,
                ndcg: null,
                avgLatencyMs: null,
                p95LatencyMs: null,
                errorReason: failure.reason
            });
            continue;
        }

        if (!datasetToIndexMap.has(datasetPath)) {
            console.log(`Skipping ${exp.name}: Index was not created during the preparation phase for ${path.basename(datasetPath)}`);
            continue;
        }

        const indexName = datasetToIndexMap.get(datasetPath)!;

        // ----- Check if we need to load new dataset data -----
        if (datasetPath !== datasetCache.datasetPath) {
            const qrelsPath = path.join(datasetPath, "qrels.tsv");
            const queriesPath = path.join(datasetPath, "queries.jsonl");

            if (!fs.existsSync(qrelsPath) || !fs.existsSync(queriesPath)) {
                console.log(`Skipping ${exp.name}: Missing files in ${datasetPath}`);
                continue;
            }

            console.log(`\nLoading dataset: ${path.basename(datasetPath)}`);
            datasetCache.qrels = load_qrels(qrelsPath);
            // Derive valid QIDs set
            const validQids = new Set(Object.keys(datasetCache.qrels));
            datasetCache.queries = await load_queries(queriesPath, validQids);

            // CRITICAL STEP: Load the index specifically for this dataset
            try {
                await client.loadIndex(indexName);
                console.log(`🔌 Connecting to index: ${indexName}`);
            } catch (error) {
                const msg = error instanceof Error ? error.message : String(error);
                const reason = msg.includes("Cloud API request failed")
                    ? "Cloud API request failed"
                    : `Failed to load index: ${msg}`;
                results.push({
                    experiment: exp.name,
                    sdkVersion,
                    datasetName: path.basename(datasetPath),
                    numQueries: 0,
                    hitRate: null,
                    mrr: null,
                    ndcg: null,
                    avgLatencyMs: null,
                    p95LatencyMs: null,
                    errorReason: reason
                });
                datasetCache.datasetPath = datasetPath;
                continue;
            }

            datasetCache.datasetPath = datasetPath;
        }

        // ----- Use Cached Data -----
        if (!datasetCache.qrels || !datasetCache.queries) {
            continue;
        }

        const stats = await run_scenario(
            client, 
            exp, 
            datasetCache.queries, 
            datasetCache.qrels, 
            indexName,
            sdkVersion
        );
        results.push(stats);
    }

    // ---------------------------------------------------------
    // PHASE 3: REPORTING
    // ---------------------------------------------------------

    // Print Results
    const header = `${'Experiment'.padEnd(25)} | ${'SDK Version'.padEnd(12)} | ${'Dataset'.padEnd(30)} | ${'HitRate'.padStart(8)} | ${'NDCG'.padStart(8)} | ${'MRR'.padStart(8)} | ${'Avg(ms)'.padStart(8)} | ${'P95(ms)'.padStart(8)} | ${'Reason'.padEnd(40)}`;
    console.log("\n" + "=".repeat(header.length));
    console.log(" EXPERIMENT RESULTS");
    console.log("=".repeat(header.length));
    console.log(header);
    console.log("-".repeat(header.length));

    for (const stats of results) {
        if (stats.errorReason) {
            const row = `${stats.experiment.padEnd(25)} | ${stats.sdkVersion.padEnd(12)} | ${stats.datasetName.padEnd(30)} | ${'N/A'.padStart(8)} | ${'N/A'.padStart(8)} | ${'N/A'.padStart(8)} | ${'N/A'.padStart(8)} | ${'N/A'.padStart(8)} | ${String(stats.errorReason).padEnd(40)}`;
            console.log(row);
        } else {
            const row = `${stats.experiment.padEnd(25)} | ${stats.sdkVersion.padEnd(12)} | ${stats.datasetName.padEnd(30)} | ${(stats.hitRate ?? 0).toFixed(3).padStart(8)} | ${(stats.ndcg ?? 0).toFixed(3).padStart(8)} | ${(stats.mrr ?? 0).toFixed(3).padStart(8)} | ${(stats.avgLatencyMs ?? 0).toFixed(1).padStart(8)} | ${(stats.p95LatencyMs ?? 0).toFixed(1).padStart(8)} | ${''.padEnd(40)}`;
            console.log(row);
        }
        console.log("-".repeat(header.length));
    }

    console.log("=".repeat(header.length));

    // ---------------------------------------------------------
    // PHASE 4: CLEANUP (Delete all created indices)
    // ---------------------------------------------------------
    console.log("\n" + "=".repeat(60));
    console.log(" CLEANING UP INDICES");
    console.log("=".repeat(60));
    
    const allIndices = new Set<string>();
    // Add indices from successfully created datasets
    for (const indexName of datasetToIndexMap.values()) {
        allIndices.add(indexName);
    }
    // Also include indices from failed datasets (they might have been created before failing)
    for (const failure of failedDatasets.values()) {
        if (failure.indexName) {
            allIndices.add(failure.indexName);
        }
    }
    
    if (allIndices.size > 0) {
        console.log(`\n🗑️  Deleting ${allIndices.size} indices...`);
        const sortedIndices = Array.from(allIndices).sort();
        for (const indexName of sortedIndices) {
            try {
                await client.deleteIndex(indexName);
                console.log(`   ✅ Deleted: ${indexName}`);
            } catch (error) {
                const msg = error instanceof Error ? error.message : String(error);
                console.log(`   ⚠️  Failed to delete ${indexName}: ${msg}`);
            }
        }
    } else {
        console.log("\n   No indices to delete.");
    }
    
    console.log("\nDone.");
}

// Execute script only when run directly under tsx/node
const isDirectRun = Boolean(
    process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href
);

if (isDirectRun) {
    main().catch(err => {
        console.error(err);
        process.exit(1);
    });
}
export const CLOUD_MANAGE_URL = 'https://service.usemoss.dev/v1/manage';
export const CLOUD_QUERY_URL = 'https://service.usemoss.dev/query';

export interface MossDocument {
	id: string;
	text: string;
	metadata?: Record<string, string>;
}

export interface MossCredentials {
	projectId: string;
	projectKey: string;
}

export interface WaitOptions {
	waitForCompletion?: boolean;
	maxWaitSeconds?: number;
}

const MANAGE_TIMEOUT_MS = 120_000;
const QUERY_TIMEOUT_MS = 60_000;
const UPLOAD_TIMEOUT_MS = 1_800_000;
const MAX_UPLOAD_RETRIES = 3;
const POLL_INTERVAL_MS = 2_000;
const MAX_CONSECUTIVE_ERRORS = 3;
const DEFAULT_MAX_WAIT_SECONDS = 300;

type ManageResponse = Record<string, unknown>;

async function manageRequest(
	credentials: MossCredentials,
	body: Record<string, unknown>,
): Promise<ManageResponse> {
	const response = await fetch(CLOUD_MANAGE_URL, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			'x-project-key': credentials.projectKey,
			'x-service-version': 'v1',
		},
		body: JSON.stringify({
			projectId: credentials.projectId,
			...body,
		}),
		signal: AbortSignal.timeout(MANAGE_TIMEOUT_MS),
	});

	const text = await response.text();
	let data: ManageResponse = {};
	if (text) {
		try {
			data = JSON.parse(text) as ManageResponse;
		} catch {
			throw new Error(`Moss API returned non-JSON response (${response.status}): ${text}`);
		}
	}

	if (!response.ok) {
		const message =
			typeof data.error === 'string' ? data.error : `Moss API error ${response.status}`;
		throw new Error(message);
	}

	return data;
}

/**
 * Serializes docs into the Moss bulk upload binary format:
 *   [MOSS (4B)] [version=1 (4B)] [docCount (4B)] [dim (4B)]
 *   [metaLen (4B)] [metadata JSON] [float32 embeddings]
 *
 * Uses dimension=0 so the control plane generates embeddings server-side.
 */
export function serializeBulkPayload(docs: MossDocument[]): ArrayBuffer {
	const metadata = docs.map(({ id, text, metadata: meta }) => ({
		id,
		text,
		...(meta ? { metadata: meta } : {}),
	}));
	const metadataBytes = new TextEncoder().encode(JSON.stringify(metadata));

	const HEADER_SIZE = 20;
	const totalSize = HEADER_SIZE + metadataBytes.length;
	const buffer = new ArrayBuffer(totalSize);
	const view = new DataView(buffer);
	const byteView = new Uint8Array(buffer);

	byteView.set([0x4d, 0x4f, 0x53, 0x53], 0); // "MOSS"
	view.setUint32(4, 1, true); // bulk format version
	view.setUint32(8, docs.length, true);
	view.setUint32(12, 0, true); // dimension=0 → server embeds
	view.setUint32(16, metadataBytes.length, true);
	byteView.set(metadataBytes, HEADER_SIZE);

	return buffer;
}

export function parseDocuments(raw: unknown): MossDocument[] {
	if (typeof raw === 'string') {
		return parseDocuments(JSON.parse(raw) as unknown);
	}

	if (!Array.isArray(raw)) {
		throw new Error('Documents must be a JSON array of { id, text, metadata? } objects');
	}

	return raw.map((doc, index) => {
		if (!doc || typeof doc !== 'object') {
			throw new Error(`Document at index ${index} must be an object`);
		}
		const record = doc as Record<string, unknown>;
		if (typeof record.id !== 'string' || typeof record.text !== 'string') {
			throw new Error(`Document at index ${index} requires string "id" and "text" fields`);
		}

		let metadata: Record<string, string> | undefined;
		if (record.metadata !== undefined) {
			if (!record.metadata || typeof record.metadata !== 'object' || Array.isArray(record.metadata)) {
				throw new Error(`Document at index ${index} metadata must be an object of string values`);
			}
			metadata = {};
			for (const [key, value] of Object.entries(record.metadata as Record<string, unknown>)) {
				if (typeof value !== 'string') {
					throw new Error(
						`Document at index ${index} metadata.${key} must be a string (got ${typeof value})`,
					);
				}
				metadata[key] = value;
			}
		}

		return { id: record.id, text: record.text, ...(metadata ? { metadata } : {}) };
	});
}

export function parseStringList(raw: unknown): string[] {
	if (Array.isArray(raw)) {
		return raw.map(String).filter(Boolean);
	}
	if (typeof raw === 'string') {
		const trimmed = raw.trim();
		if (!trimmed) return [];
		if (trimmed.startsWith('[')) {
			return parseStringList(JSON.parse(trimmed) as unknown);
		}
		return trimmed
			.split(/[\n,]/)
			.map((part) => part.trim())
			.filter(Boolean);
	}
	return [];
}

async function uploadWithRetries(uploadUrl: string, payload: ArrayBuffer): Promise<void> {
	let lastStatus = 0;

	for (let attempt = 0; attempt < MAX_UPLOAD_RETRIES; attempt++) {
		const response = await fetch(uploadUrl, {
			method: 'PUT',
			body: payload,
			headers: { 'Content-Type': 'application/octet-stream' },
			signal: AbortSignal.timeout(UPLOAD_TIMEOUT_MS),
		});
		lastStatus = response.status;
		if (response.ok) return;
		if (response.status < 500) break;
		if (attempt < MAX_UPLOAD_RETRIES - 1) {
			await new Promise((resolve) => setTimeout(resolve, 1000 * 2 ** attempt));
		}
	}

	throw new Error(`Failed to upload Moss index payload (HTTP ${lastStatus})`);
}

export async function pollJobUntilComplete(
	credentials: MossCredentials,
	jobId: string,
	indexName: string,
	docCount: number,
	maxWaitSeconds: number = DEFAULT_MAX_WAIT_SECONDS,
): Promise<Record<string, unknown>> {
	const maxWaitMs = Math.max(1, maxWaitSeconds) * 1000;
	const start = Date.now();
	let consecutiveErrors = 0;

	while (Date.now() - start < maxWaitMs) {
		let status: ManageResponse;
		try {
			status = await manageRequest(credentials, {
				action: 'getJobStatus',
				jobId,
			});
			consecutiveErrors = 0;
		} catch (error) {
			consecutiveErrors += 1;
			if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
				throw new Error(
					`Job status polling failed after ${MAX_CONSECUTIVE_ERRORS} consecutive errors: ${
						error instanceof Error ? error.message : String(error)
					}`,
				);
			}
			await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
			continue;
		}

		const jobStatus = String(status.status ?? '')
			.toLowerCase()
			.replace(/\s+/g, '_');

		if (jobStatus === 'completed') {
			return { jobId, indexName, docCount, status: 'completed' };
		}
		if (jobStatus === 'failed') {
			throw new Error(`Moss job failed: ${String(status.error ?? 'unknown error')}`);
		}

		await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
	}

	throw new Error(
		`Moss job timed out after ${maxWaitSeconds}s (job ${jobId}). Use Get Job Status to keep polling.`,
	);
}

async function maybeWaitForJob(
	credentials: MossCredentials,
	response: ManageResponse,
	indexName: string,
	docCount: number,
	wait?: WaitOptions,
): Promise<Record<string, unknown>> {
	const jobId = typeof response.jobId === 'string' ? response.jobId : '';
	if (!wait?.waitForCompletion || !jobId) {
		return response;
	}

	return pollJobUntilComplete(
		credentials,
		jobId,
		indexName,
		docCount,
		wait.maxWaitSeconds ?? DEFAULT_MAX_WAIT_SECONDS,
	);
}

export async function createIndex(
	credentials: MossCredentials,
	indexName: string,
	docs: MossDocument[],
	modelId: string,
	wait?: WaitOptions,
): Promise<Record<string, unknown>> {
	if (!docs.length) {
		throw new Error('Create Index requires at least one document');
	}

	const init = await manageRequest(credentials, {
		action: 'initUpload',
		indexName,
		modelId,
		docCount: docs.length,
		dimension: 0,
	});

	const jobId = String(init.jobId ?? '');
	const uploadUrl = String(init.uploadUrl ?? '');
	if (!jobId || !uploadUrl) {
		throw new Error('Moss initUpload did not return jobId/uploadUrl');
	}

	await uploadWithRetries(uploadUrl, serializeBulkPayload(docs));

	const started = await manageRequest(credentials, {
		action: 'startBuild',
		jobId,
	});

	return maybeWaitForJob(
		credentials,
		{ ...started, jobId, indexName, docCount: docs.length },
		indexName,
		docs.length,
		wait,
	);
}

export async function addDocs(
	credentials: MossCredentials,
	indexName: string,
	docs: MossDocument[],
	upsert: boolean,
	wait?: WaitOptions,
): Promise<Record<string, unknown>> {
	if (!docs.length) {
		throw new Error('Add Documents requires at least one document');
	}

	const response = await manageRequest(credentials, {
		action: 'addDocs',
		indexName,
		docs,
		options: { upsert },
	});

	return maybeWaitForJob(credentials, response, indexName, docs.length, wait);
}

export async function deleteDocs(
	credentials: MossCredentials,
	indexName: string,
	docIds: string[],
	wait?: WaitOptions,
): Promise<Record<string, unknown>> {
	if (!docIds.length) {
		throw new Error('Delete Documents requires at least one document ID');
	}

	const response = await manageRequest(credentials, {
		action: 'deleteDocs',
		indexName,
		docIds,
	});

	return maybeWaitForJob(credentials, response, indexName, docIds.length, wait);
}

export async function getDocs(
	credentials: MossCredentials,
	indexName: string,
	docIds?: string[],
): Promise<unknown> {
	return manageRequest(credentials, {
		action: 'getDocs',
		indexName,
		...(docIds?.length ? { docIds } : {}),
	});
}

export async function listIndexes(credentials: MossCredentials): Promise<unknown> {
	return manageRequest(credentials, { action: 'listIndexes' });
}

export async function getIndex(
	credentials: MossCredentials,
	indexName: string,
): Promise<Record<string, unknown>> {
	return manageRequest(credentials, { action: 'getIndex', indexName });
}

export async function deleteIndex(
	credentials: MossCredentials,
	indexName: string,
): Promise<Record<string, unknown>> {
	return manageRequest(credentials, { action: 'deleteIndex', indexName });
}

export async function getJobStatus(
	credentials: MossCredentials,
	jobId: string,
): Promise<Record<string, unknown>> {
	return manageRequest(credentials, { action: 'getJobStatus', jobId });
}

export async function queryIndex(
	credentials: MossCredentials,
	indexName: string,
	query: string,
	topK: number,
): Promise<Record<string, unknown>> {
	const response = await fetch(CLOUD_QUERY_URL, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
		},
		body: JSON.stringify({
			query,
			indexName,
			projectId: credentials.projectId,
			projectKey: credentials.projectKey,
			topK,
		}),
		signal: AbortSignal.timeout(QUERY_TIMEOUT_MS),
	});

	const text = await response.text();
	let data: Record<string, unknown> = {};
	if (text) {
		try {
			data = JSON.parse(text) as Record<string, unknown>;
		} catch {
			throw new Error(`Moss query returned non-JSON response (${response.status}): ${text}`);
		}
	}

	if (!response.ok) {
		const message =
			typeof data.error === 'string' ? data.error : `Moss query error ${response.status}`;
		throw new Error(message);
	}

	return data;
}

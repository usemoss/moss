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

function extractErrorMessage(data: unknown, status: number, fallbackPrefix: string): string {
	if (data && typeof data === 'object' && !Array.isArray(data)) {
		const error = (data as Record<string, unknown>).error;
		if (typeof error === 'string' && error.trim()) {
			return error;
		}
		const message = (data as Record<string, unknown>).message;
		if (typeof message === 'string' && message.trim()) {
			return message;
		}
	}
	return `${fallbackPrefix} ${status}`;
}

async function parseResponseBody(response: Response): Promise<unknown> {
	const text = await response.text();
	if (!text) {
		return {};
	}
	try {
		return JSON.parse(text) as unknown;
	} catch {
		const snippet = text.replace(/\s+/g, ' ').trim().slice(0, 200);
		throw new Error(
			`Moss API returned non-JSON response (${response.status}): ${snippet || '(empty)'}`,
		);
	}
}

function isRetryableTransportError(error: unknown): boolean {
	if (!(error instanceof Error)) {
		return false;
	}
	const name = error.name;
	const message = error.message.toLowerCase();
	return (
		name === 'AbortError' ||
		name === 'TimeoutError' ||
		message.includes('fetch failed') ||
		message.includes('network') ||
		message.includes('econnreset') ||
		message.includes('etimedout') ||
		message.includes('socket')
	);
}

const MAX_RETRY_AFTER_MS = 60_000;

/** Parse Retry-After as delay-seconds or HTTP-date; returns wait milliseconds. */
export function parseRetryAfterMs(header: string | null, nowMs: number = Date.now()): number | undefined {
	if (!header) return undefined;
	const trimmed = header.trim();
	if (!trimmed) return undefined;

	if (/^\d+$/.test(trimmed)) {
		return Math.min(MAX_RETRY_AFTER_MS, Math.max(0, Number(trimmed) * 1000));
	}

	const dateMs = Date.parse(trimmed);
	if (Number.isNaN(dateMs)) return undefined;
	return Math.min(MAX_RETRY_AFTER_MS, Math.max(0, dateMs - nowMs));
}

export async function manageRequest(
	credentials: MossCredentials,
	body: Record<string, unknown>,
	timeoutMs: number = MANAGE_TIMEOUT_MS,
): Promise<unknown> {
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
		signal: AbortSignal.timeout(Math.max(1, timeoutMs)),
	});

	const data = await parseResponseBody(response);

	if (!response.ok) {
		throw new Error(extractErrorMessage(data, response.status, 'Moss API error'));
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
	let value = raw;
	if (typeof value === 'string') {
		try {
			value = JSON.parse(value) as unknown;
		} catch {
			throw new Error('Documents must be valid JSON (array of { id, text, metadata? } objects)');
		}
	}

	if (!Array.isArray(value)) {
		throw new Error('Documents must be a JSON array of { id, text, metadata? } objects');
	}

	return value.map((doc, index) => {
		if (!doc || typeof doc !== 'object') {
			throw new Error(`Document at index ${index} must be an object`);
		}
		const record = doc as Record<string, unknown>;

		const id =
			typeof record.id === 'string'
				? record.id
				: typeof record.id === 'number'
					? String(record.id)
					: null;
		const text =
			typeof record.text === 'string'
				? record.text
				: typeof record.text === 'number'
					? String(record.text)
					: null;

		if (id === null || text === null) {
			throw new Error(`Document at index ${index} requires string "id" and "text" fields`);
		}

		let metadata: Record<string, string> | undefined;
		if (record.metadata !== undefined) {
			if (!record.metadata || typeof record.metadata !== 'object' || Array.isArray(record.metadata)) {
				throw new Error(`Document at index ${index} metadata must be an object of string values`);
			}
			metadata = {};
			for (const [key, metaValue] of Object.entries(record.metadata as Record<string, unknown>)) {
				if (typeof metaValue === 'string') {
					metadata[key] = metaValue;
				} else if (typeof metaValue === 'number' || typeof metaValue === 'boolean') {
					metadata[key] = String(metaValue);
				} else {
					throw new Error(
						`Document at index ${index} metadata.${key} must be a string (got ${typeof metaValue})`,
					);
				}
			}
		}

		return { id, text, ...(metadata ? { metadata } : {}) };
	});
}

function normalizeIdToken(value: unknown, index: number): string {
	if (typeof value === 'string') {
		const trimmed = value.trim();
		if (!trimmed) {
			throw new Error(`Document ID at index ${index} is empty`);
		}
		return trimmed;
	}
	if (typeof value === 'number' && Number.isFinite(value)) {
		return String(value);
	}
	throw new Error(
		`Document ID at index ${index} must be a string or number (got ${
			value === null ? 'null' : typeof value
		})`,
	);
}

export function parseStringList(raw: unknown): string[] {
	if (Array.isArray(raw)) {
		return raw.map((value, index) => normalizeIdToken(value, index));
	}
	if (typeof raw === 'string') {
		const trimmed = raw.trim();
		if (!trimmed) return [];
		if (trimmed.startsWith('[')) {
			try {
				return parseStringList(JSON.parse(trimmed) as unknown);
			} catch (error) {
				if (error instanceof Error && error.message.startsWith('Document ID')) {
					throw error;
				}
				throw new Error('Document IDs JSON array is invalid');
			}
		}
		return trimmed
			.split(/[\n,]/)
			.map((part) => part.trim())
			.filter(Boolean);
	}
	return [];
}

/** Normalize API payloads so n8n returnJsonArray always gets an object or object[]. */
export function normalizeExecutionData(data: unknown): Record<string, unknown> | Record<string, unknown>[] {
	if (Array.isArray(data)) {
		return data.map((item, index) => {
			if (item && typeof item === 'object' && !Array.isArray(item)) {
				return item as Record<string, unknown>;
			}
			return { value: item, index };
		});
	}

	if (data && typeof data === 'object') {
		return data as Record<string, unknown>;
	}

	return { result: data };
}

async function uploadWithRetries(uploadUrl: string, payload: ArrayBuffer): Promise<void> {
	let lastError: Error | undefined;
	const body = Buffer.from(payload);

	for (let attempt = 0; attempt < MAX_UPLOAD_RETRIES; attempt++) {
		let retryDelayMs = 1000 * 2 ** attempt;

		try {
			const response = await fetch(uploadUrl, {
				method: 'PUT',
				body,
				headers: { 'Content-Type': 'application/octet-stream' },
				signal: AbortSignal.timeout(UPLOAD_TIMEOUT_MS),
			});

			const retryAfterMs = parseRetryAfterMs(response.headers.get('Retry-After'));

			// Drain/cancel the body so keep-alive sockets are released promptly.
			await response.arrayBuffer().catch(() => undefined);

			if (response.ok) return;

			lastError = new Error(`Failed to upload Moss index payload (HTTP ${response.status})`);
			const retryableStatus = response.status === 429 || response.status >= 500;
			if (!retryableStatus) {
				throw lastError;
			}
			if (retryAfterMs !== undefined) {
				retryDelayMs = retryAfterMs;
			}
		} catch (error) {
			if (
				error instanceof Error &&
				/HTTP [4]\d\d/.test(error.message) &&
				!/HTTP 429/.test(error.message)
			) {
				throw error;
			}
			lastError =
				error instanceof Error
					? error
					: new Error(`Failed to upload Moss index payload: ${String(error)}`);
			if (
				!isRetryableTransportError(error) &&
				!/HTTP 5\d\d/.test(lastError.message) &&
				!/HTTP 429/.test(lastError.message)
			) {
				throw lastError;
			}
		}

		if (attempt < MAX_UPLOAD_RETRIES - 1) {
			await new Promise((resolve) => setTimeout(resolve, retryDelayMs));
		}
	}

	throw lastError ?? new Error('Failed to upload Moss index payload');
}

function normalizeJobStatus(status: unknown): string {
	return String(status ?? '')
		.trim()
		.toLowerCase()
		.replace(/\s+/g, '_');
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

	while (true) {
		const elapsed = Date.now() - start;
		const remainingMs = maxWaitMs - elapsed;
		if (remainingMs <= 0) {
			break;
		}

		let statusPayload: unknown;
		try {
			statusPayload = await manageRequest(
				credentials,
				{
					action: 'getJobStatus',
					jobId,
				},
				Math.min(MANAGE_TIMEOUT_MS, remainingMs),
			);
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
			const sleepMs = Math.min(POLL_INTERVAL_MS, Math.max(0, maxWaitMs - (Date.now() - start)));
			if (sleepMs <= 0) break;
			await new Promise((resolve) => setTimeout(resolve, sleepMs));
			continue;
		}

		const status =
			statusPayload && typeof statusPayload === 'object' && !Array.isArray(statusPayload)
				? (statusPayload as Record<string, unknown>)
				: {};
		const jobStatus = normalizeJobStatus(status.status);
		const compact = jobStatus.replace(/_/g, '');

		if (jobStatus === 'completed' || compact === 'completed') {
			return { jobId, indexName, docCount, status: 'completed' };
		}
		if (jobStatus === 'failed' || compact === 'failed') {
			throw new Error(`Moss job failed: ${String(status.error ?? 'unknown error')}`);
		}

		const sleepMs = Math.min(POLL_INTERVAL_MS, Math.max(0, maxWaitMs - (Date.now() - start)));
		if (sleepMs <= 0) break;
		await new Promise((resolve) => setTimeout(resolve, sleepMs));
	}

	throw new Error(
		`Moss job timed out after ${maxWaitSeconds}s (job ${jobId}). Use Get Job Status to keep polling.`,
	);
}

async function maybeWaitForJob(
	credentials: MossCredentials,
	response: unknown,
	indexName: string,
	docCount: number,
	wait?: WaitOptions,
): Promise<Record<string, unknown>> {
	const payload =
		response && typeof response === 'object' && !Array.isArray(response)
			? (response as Record<string, unknown>)
			: { result: response };

	const jobId = typeof payload.jobId === 'string' ? payload.jobId : '';
	if (!wait?.waitForCompletion || !jobId) {
		return payload;
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

	const init = (await manageRequest(credentials, {
		action: 'initUpload',
		indexName,
		modelId,
		docCount: docs.length,
		dimension: 0,
	})) as Record<string, unknown>;

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
		{ ...(started as Record<string, unknown>), jobId, indexName, docCount: docs.length },
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
		...(docIds?.length ? { options: { docIds } } : {}),
	});
}

export async function listIndexes(credentials: MossCredentials): Promise<unknown> {
	return manageRequest(credentials, { action: 'listIndexes' });
}

export async function getIndex(
	credentials: MossCredentials,
	indexName: string,
): Promise<Record<string, unknown>> {
	return (await manageRequest(credentials, { action: 'getIndex', indexName })) as Record<
		string,
		unknown
	>;
}

export async function deleteIndex(
	credentials: MossCredentials,
	indexName: string,
): Promise<Record<string, unknown>> {
	return (await manageRequest(credentials, { action: 'deleteIndex', indexName })) as Record<
		string,
		unknown
	>;
}

export async function getJobStatus(
	credentials: MossCredentials,
	jobId: string,
): Promise<Record<string, unknown>> {
	return (await manageRequest(credentials, { action: 'getJobStatus', jobId })) as Record<
		string,
		unknown
	>;
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

	const data = await parseResponseBody(response);

	if (!response.ok) {
		throw new Error(extractErrorMessage(data, response.status, 'Moss query error'));
	}

	if (data && typeof data === 'object' && !Array.isArray(data)) {
		return data as Record<string, unknown>;
	}

	return { result: data };
}

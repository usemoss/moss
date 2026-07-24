import { afterEach, describe, expect, it, vi } from 'vitest';

import {
	CLOUD_MANAGE_URL,
	CLOUD_QUERY_URL,
	addDocs,
	createIndex,
	getDocs,
	listIndexes,
	normalizeExecutionData,
	parseDocuments,
	parseRetryAfterMs,
	parseStringList,
	queryIndex,
	serializeBulkPayload,
} from '../nodes/Moss/GenericFunctions';

function decodeHeader(buf: ArrayBuffer) {
	const view = new DataView(buf);
	const magic = new TextDecoder().decode(new Uint8Array(buf, 0, 4));
	return {
		magic,
		version: view.getUint32(4, true),
		docCount: view.getUint32(8, true),
		dimension: view.getUint32(12, true),
		metadataLen: view.getUint32(16, true),
	};
}

const credentials = {
	projectId: 'project-123',
	projectKey: 'key-abc',
};

afterEach(() => {
	vi.unstubAllGlobals();
	vi.restoreAllMocks();
});

describe('serializeBulkPayload', () => {
	it('writes MOSS magic, version 1, and dimension 0 for text-only docs', () => {
		const buf = serializeBulkPayload([
			{ id: 'd1', text: 'hello' },
			{ id: 'd2', text: 'world', metadata: { source: 'faq' } },
		]);
		const header = decodeHeader(buf);
		expect(header.magic).toBe('MOSS');
		expect(header.version).toBe(1);
		expect(header.docCount).toBe(2);
		expect(header.dimension).toBe(0);
		expect(buf.byteLength).toBe(20 + header.metadataLen);

		const metadata = JSON.parse(
			new TextDecoder().decode(new Uint8Array(buf, 20, header.metadataLen)),
		);
		expect(metadata).toEqual([
			{ id: 'd1', text: 'hello' },
			{ id: 'd2', text: 'world', metadata: { source: 'faq' } },
		]);
	});
});

describe('parseDocuments', () => {
	it('parses JSON string and coerces numeric ids/metadata', () => {
		expect(
			parseDocuments('[{"id":1,"text":"one","metadata":{"k":2,"ok":true}}]'),
		).toEqual([{ id: '1', text: 'one', metadata: { k: '2', ok: 'true' } }]);
	});

	it('rejects invalid JSON and non-string object metadata', () => {
		expect(() => parseDocuments('{bad')).toThrow(/valid JSON/);
		expect(() =>
			parseDocuments([{ id: 'a', text: 'one', metadata: { nested: { x: 1 } } }]),
		).toThrow(/metadata\.nested must be a string/);
	});
});

describe('parseStringList', () => {
	it('parses comma-separated, newline, and JSON arrays', () => {
		expect(parseStringList('a, b, c')).toEqual(['a', 'b', 'c']);
		expect(parseStringList('a\nb')).toEqual(['a', 'b']);
		expect(parseStringList('["x","y"]')).toEqual(['x', 'y']);
		expect(parseStringList('')).toEqual([]);
		expect(parseStringList([1, '  two  '])).toEqual(['1', 'two']);
	});

	it('rejects null/boolean/object IDs instead of stringifying them', () => {
		expect(() => parseStringList([null])).toThrow(/must be a string or number/);
		expect(() => parseStringList([true])).toThrow(/must be a string or number/);
		expect(() => parseStringList([{}])).toThrow(/must be a string or number/);
		expect(() => parseStringList(['  '])).toThrow(/empty/);
	});
});

describe('parseRetryAfterMs', () => {
	it('parses delay-seconds and HTTP-date forms with a 60s cap', () => {
		expect(parseRetryAfterMs('3')).toBe(3000);
		expect(parseRetryAfterMs('120')).toBe(60_000);

		const now = Date.parse('Wed, 21 Oct 2015 07:28:00 GMT');
		expect(parseRetryAfterMs('Wed, 21 Oct 2015 07:28:05 GMT', now)).toBe(5000);
		expect(parseRetryAfterMs('Wed, 21 Oct 2015 07:30:00 GMT', now)).toBe(60_000);
		expect(parseRetryAfterMs('not-a-date')).toBeUndefined();
		expect(parseRetryAfterMs(null)).toBeUndefined();
	});
});

describe('normalizeExecutionData', () => {
	it('passes through objects and maps arrays for n8n items', () => {
		expect(normalizeExecutionData({ ok: true })).toEqual({ ok: true });
		expect(normalizeExecutionData([{ name: 'a' }, { name: 'b' }])).toEqual([
			{ name: 'a' },
			{ name: 'b' },
		]);
		expect(normalizeExecutionData([])).toEqual([]);
	});
});

describe('HTTP helpers (mocked)', () => {
	it('listIndexes posts manage action with auth headers', async () => {
		const fetchMock = vi.fn(async () =>
			new Response(JSON.stringify([{ name: 'support-faq', docCount: 2 }]), {
				status: 200,
				headers: { 'Content-Type': 'application/json' },
			}),
		);
		vi.stubGlobal('fetch', fetchMock);

		const result = await listIndexes(credentials);
		expect(result).toEqual([{ name: 'support-faq', docCount: 2 }]);
		expect(fetchMock).toHaveBeenCalledWith(
			CLOUD_MANAGE_URL,
			expect.objectContaining({
				method: 'POST',
				headers: expect.objectContaining({
					'x-project-key': 'key-abc',
					'x-service-version': 'v1',
				}),
			}),
		);
		const body = JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string);
		expect(body).toEqual({
			projectId: 'project-123',
			action: 'listIndexes',
		});
	});

	it('queryIndex posts to cloud query endpoint', async () => {
		const fetchMock = vi.fn(async () =>
			new Response(
				JSON.stringify({
					query: 'refunds',
					docs: [{ id: '1', text: '30 day returns', score: 0.9 }],
				}),
				{ status: 200, headers: { 'Content-Type': 'application/json' } },
			),
		);
		vi.stubGlobal('fetch', fetchMock);

		const result = await queryIndex(credentials, 'support-faq', 'refunds', 3);
		expect(result.docs).toHaveLength(1);
		expect(fetchMock).toHaveBeenCalledWith(
			CLOUD_QUERY_URL,
			expect.objectContaining({ method: 'POST' }),
		);
		const body = JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string);
		expect(body).toEqual({
			query: 'refunds',
			indexName: 'support-faq',
			projectId: 'project-123',
			projectKey: 'key-abc',
			topK: 3,
		});
	});

	it('createIndex runs initUpload → PUT → startBuild → poll completed', async () => {
		const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
			if (url === CLOUD_MANAGE_URL) {
				const body = JSON.parse(String(init?.body)) as { action: string };
				if (body.action === 'initUpload') {
					return new Response(
						JSON.stringify({
							jobId: 'job-1',
							uploadUrl: 'https://upload.example/put',
						}),
						{ status: 200 },
					);
				}
				if (body.action === 'startBuild') {
					return new Response(JSON.stringify({ jobId: 'job-1', status: 'building' }), {
						status: 200,
					});
				}
				if (body.action === 'getJobStatus') {
					return new Response(
						JSON.stringify({ jobId: 'job-1', status: 'completed', progress: 100 }),
						{ status: 200 },
					);
				}
			}
			if (url === 'https://upload.example/put') {
				expect(init?.method).toBe('PUT');
				expect(init?.body).toBeInstanceOf(Buffer);
				return new Response(null, { status: 200 });
			}
			return new Response(JSON.stringify({ error: `unexpected ${url}` }), { status: 500 });
		});
		vi.stubGlobal('fetch', fetchMock);

		const result = await createIndex(
			credentials,
			'faqs',
			[{ id: '1', text: 'hello' }],
			'moss-minilm',
			{ waitForCompletion: true, maxWaitSeconds: 5 },
		);

		expect(result).toEqual({
			jobId: 'job-1',
			indexName: 'faqs',
			docCount: 1,
			status: 'completed',
		});
		expect(fetchMock).toHaveBeenCalled();
	});

	it('createIndex retries upload on HTTP 429 then succeeds', async () => {
		let uploadAttempts = 0;
		const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
			if (url === CLOUD_MANAGE_URL) {
				const body = JSON.parse(String(init?.body)) as { action: string };
				if (body.action === 'initUpload') {
					return new Response(
						JSON.stringify({
							jobId: 'job-429',
							uploadUrl: 'https://upload.example/put-429',
						}),
						{ status: 200 },
					);
				}
				if (body.action === 'startBuild') {
					return new Response(JSON.stringify({ jobId: 'job-429', status: 'building' }), {
						status: 200,
					});
				}
				if (body.action === 'getJobStatus') {
					return new Response(
						JSON.stringify({ jobId: 'job-429', status: 'completed', progress: 100 }),
						{ status: 200 },
					);
				}
			}
			if (url === 'https://upload.example/put-429') {
				uploadAttempts += 1;
				if (uploadAttempts === 1) {
					return new Response('slow down', {
						status: 429,
						headers: { 'Retry-After': '0' },
					});
				}
				return new Response(null, { status: 200 });
			}
			return new Response(JSON.stringify({ error: `unexpected ${url}` }), { status: 500 });
		});
		vi.stubGlobal('fetch', fetchMock);

		const result = await createIndex(
			credentials,
			'faqs',
			[{ id: '1', text: 'hello' }],
			'moss-minilm',
			{ waitForCompletion: true, maxWaitSeconds: 5 },
		);

		expect(uploadAttempts).toBe(2);
		expect(result.status).toBe('completed');
	});

	it('addDocs returns job payload when wait is disabled', async () => {
		const fetchMock = vi.fn(async () =>
			new Response(JSON.stringify({ jobId: 'job-2', status: 'building' }), { status: 200 }),
		);
		vi.stubGlobal('fetch', fetchMock);

		const result = await addDocs(
			credentials,
			'faqs',
			[{ id: '2', text: 'more' }],
			true,
			{ waitForCompletion: false },
		);
		expect(result).toEqual({ jobId: 'job-2', status: 'building' });
	});

	it('getDocs nests docIds under options', async () => {
		const fetchMock = vi.fn(async () =>
			new Response(JSON.stringify([{ id: 'a', text: 'hello' }]), { status: 200 }),
		);
		vi.stubGlobal('fetch', fetchMock);

		await getDocs(credentials, 'faqs', ['a', 'b']);
		const body = JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string);
		expect(body).toEqual({
			projectId: 'project-123',
			action: 'getDocs',
			indexName: 'faqs',
			options: { docIds: ['a', 'b'] },
		});
	});

	it('surfaces API error messages from manage requests', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () =>
				new Response(JSON.stringify({ error: 'Index not found', action: 'getIndex' }), {
					status: 404,
				}),
			),
		);

		await expect(listIndexes(credentials)).rejects.toThrow('Index not found');
	});
});

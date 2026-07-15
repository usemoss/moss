import { describe, expect, it } from 'vitest';

import {
	parseDocuments,
	parseStringList,
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
	it('parses JSON string and object arrays', () => {
		expect(
			parseDocuments('[{"id":"a","text":"one","metadata":{"k":"v"}}]'),
		).toEqual([{ id: 'a', text: 'one', metadata: { k: 'v' } }]);
	});

	it('rejects non-string metadata values', () => {
		expect(() =>
			parseDocuments([{ id: 'a', text: 'one', metadata: { score: 1 } }]),
		).toThrow(/metadata\.score must be a string/);
	});
});

describe('parseStringList', () => {
	it('parses comma-separated, newline, and JSON arrays', () => {
		expect(parseStringList('a, b, c')).toEqual(['a', 'b', 'c']);
		expect(parseStringList('a\nb')).toEqual(['a', 'b']);
		expect(parseStringList('["x","y"]')).toEqual(['x', 'y']);
		expect(parseStringList('')).toEqual([]);
	});
});

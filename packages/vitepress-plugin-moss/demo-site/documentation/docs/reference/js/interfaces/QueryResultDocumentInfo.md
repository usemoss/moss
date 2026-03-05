[**@inferedge/moss v1.0.0-beta.7**](../README.md)

***

[@inferedge/moss](../globals.md) / QueryResultDocumentInfo

# Interface: QueryResultDocumentInfo

Document result from a query with similarity score.

## Extends

- [`DocumentInfo`](DocumentInfo.md)

## Properties

| Property | Type | Description | Inherited from |
| ------ | ------ | ------ | ------ |
| <a id="property-id"></a> `id` | `string` | Unique identifier within an index. | [`DocumentInfo`](DocumentInfo.md).[`id`](DocumentInfo.md#property-id) |
| <a id="property-text"></a> `text` | `string` | REQUIRED canonical text to embed/search. | [`DocumentInfo`](DocumentInfo.md).[`text`](DocumentInfo.md#property-text) |
| <a id="property-metadata"></a> `metadata?` | `Record`\<`string`, `string`\> | Optional metadata associated with the document. | [`DocumentInfo`](DocumentInfo.md).[`metadata`](DocumentInfo.md#property-metadata) |
| <a id="property-embedding"></a> `embedding?` | `number`[] | Optional caller-provided embedding vector. | [`DocumentInfo`](DocumentInfo.md).[`embedding`](DocumentInfo.md#property-embedding) |
| <a id="property-score"></a> `score` | `number` | Similarity score (0-1, higher = more similar). | - |

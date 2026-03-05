[**@inferedge/moss v1.0.0-beta.7**](../README.md)

***

[@inferedge/moss](../globals.md) / QueryOptions

# Interface: QueryOptions

Optional parameters for semantic queries.

## Properties

| Property | Type | Description |
| ------ | ------ | ------ |
| <a id="property-embedding"></a> `embedding?` | `number`[] | Caller-provided embedding vector. When supplied, the service/client skips embedding generation. |
| <a id="property-topk"></a> `topK?` | `number` | Number of top results to return. Overrides method-level defaults. |
| <a id="property-filter"></a> `filter?` | [`MetadataFilter`](../type-aliases/MetadataFilter.md) | - |

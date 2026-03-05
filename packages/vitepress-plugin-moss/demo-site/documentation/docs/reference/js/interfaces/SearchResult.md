[**@inferedge/moss v1.0.0-beta.7**](../README.md)

***

[@inferedge/moss](../globals.md) / SearchResult

# Interface: SearchResult

Search operation result.

## Properties

| Property | Type | Description |
| ------ | ------ | ------ |
| <a id="property-docs"></a> `docs` | [`QueryResultDocumentInfo`](QueryResultDocumentInfo.md)[] | Matching documents ordered by similarity score. |
| <a id="property-query"></a> `query` | `string` | The original search query. |
| <a id="property-indexname"></a> `indexName?` | `string` | Name of the index that was searched. |
| <a id="property-timetakeninms"></a> `timeTakenInMs?` | `number` | Time taken to execute the search in milliseconds. |

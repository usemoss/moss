[**@inferedge/moss v1.0.0-beta.7**](../README.md)

***

[@inferedge/moss](../globals.md) / MutationResult

# Interface: MutationResult

Result of an async mutation operation (createIndex, addDocs, deleteDocs).
Returned after the operation completes (polling is handled internally).

## Properties

| Property | Type |
| ------ | ------ |
| <a id="property-jobid"></a> `jobId` | `string` |
| <a id="property-indexname"></a> `indexName` | `string` |
| <a id="property-doccount"></a> `docCount` | `number` |

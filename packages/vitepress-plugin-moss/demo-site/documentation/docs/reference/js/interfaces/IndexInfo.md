[**@inferedge/moss v1.0.0-beta.7**](../README.md)

***

[@inferedge/moss](../globals.md) / IndexInfo

# Interface: IndexInfo

Information about an index including metadata and status.

## Properties

| Property | Type | Description |
| ------ | ------ | ------ |
| <a id="property-id"></a> `id` | `string` | Unique identifier of the index. |
| <a id="property-name"></a> `name` | `string` | Human-readable name of the index. |
| <a id="property-version"></a> `version` | `string` \| `null` | Index build/format version (semver). |
| <a id="property-status"></a> `status` | `"NotStarted"` \| `"Building"` \| `"Ready"` \| `"Failed"` | Current status of the index. |
| <a id="property-doccount"></a> `docCount` | `number` | Number of documents in the index. |
| <a id="property-createdat"></a> `createdAt` | `string` | When the index was created. |
| <a id="property-updatedat"></a> `updatedAt` | `string` | When the index was last updated. |
| <a id="property-model"></a> `model` | [`ModelRef`](ModelRef.md) | Model used for embeddings. |

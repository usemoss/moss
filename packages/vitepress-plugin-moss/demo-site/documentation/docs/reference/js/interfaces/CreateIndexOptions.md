[**@inferedge/moss v1.0.0-beta.7**](../README.md)

***

[@inferedge/moss](../globals.md) / CreateIndexOptions

# Interface: CreateIndexOptions

Options for creating an index.

## Properties

| Property | Type | Description |
| ------ | ------ | ------ |
| <a id="property-modelid"></a> `modelId?` | `string` | Embedding model to use. Defaults to "moss-minilm", or "custom" if documents have pre-computed embeddings. |
| <a id="property-onprogress"></a> `onProgress?` | (`progress`) => `void` | Callback invoked with progress updates (~every 2s) while the server is processing. |

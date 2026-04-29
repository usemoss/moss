---
title: "DocumentInfo (JS)"
---

[**@moss-dev/moss-web v1.0.0**](../README.md)

***

[@moss-dev/moss-web](../globals.md) / DocumentInfo

# Interface: DocumentInfo

Document that can be indexed and retrieved.

## Extended by

- [`QueryResultDocumentInfo`](QueryResultDocumentInfo.md)

## Properties

| Property | Type | Description |
| ------ | ------ | ------ |
| <a id="property-id"></a> `id` | `string` | Unique identifier within an index. |
| <a id="property-text"></a> `text` | `string` | REQUIRED canonical text to embed/search. |
| <a id="property-metadata"></a> `metadata?` | `Record`\<`string`, `string`\> | Optional metadata associated with the document. |
| <a id="property-embedding"></a> `embedding?` | `number`[] | Optional caller-provided embedding vector. |

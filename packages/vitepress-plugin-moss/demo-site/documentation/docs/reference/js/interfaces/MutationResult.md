---
title: "MutationResult (JS)"
---

[**@moss-dev/moss-web v1.0.0**](../README.md)

***

[@moss-dev/moss-web](../globals.md) / MutationResult

# Interface: MutationResult

Result of an async mutation operation (createIndex, addDocs, deleteDocs).
Returned after the operation completes (polling is handled internally).

## Properties

| Property | Type |
| ------ | ------ |
| <a id="property-jobid"></a> `jobId` | `string` |
| <a id="property-indexname"></a> `indexName` | `string` |
| <a id="property-doccount"></a> `docCount` | `number` |

---
title: "MutationOptions (JS)"
---

[**@moss-dev/moss-web v1.0.0**](../README.md)

***

[@moss-dev/moss-web](../globals.md) / MutationOptions

# Interface: MutationOptions

Options for async mutation operations (addDocs, deleteDocs).

## Properties

| Property | Type | Description |
| ------ | ------ | ------ |
| <a id="property-upsert"></a> `upsert?` | `boolean` | Whether to update existing documents with the same ID. Only applies to addDocs. **Default** `true` |
| <a id="property-onprogress"></a> `onProgress?` | (`progress`) => `void` | Callback invoked with progress updates (~every 2s) while the server is processing. |

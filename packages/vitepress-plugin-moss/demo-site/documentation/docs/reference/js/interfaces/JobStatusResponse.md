---
title: "JobStatusResponse (JS)"
---

[**@moss-dev/moss-web v1.0.0**](../README.md)

***

[@moss-dev/moss-web](../globals.md) / JobStatusResponse

# Interface: JobStatusResponse

Full job status response from getJobStatus.

## Properties

| Property | Type |
| ------ | ------ |
| <a id="property-jobid"></a> `jobId` | `string` |
| <a id="property-status"></a> `status` | [`JobStatus`](../type-aliases/JobStatus.md) |
| <a id="property-progress"></a> `progress` | `number` |
| <a id="property-currentphase"></a> `currentPhase` | [`JobPhase`](../type-aliases/JobPhase.md) \| `null` |
| <a id="property-error"></a> `error?` | `string` \| `null` |
| <a id="property-createdat"></a> `createdAt` | `string` |
| <a id="property-updatedat"></a> `updatedAt` | `string` |
| <a id="property-completedat"></a> `completedAt` | `string` \| `null` |

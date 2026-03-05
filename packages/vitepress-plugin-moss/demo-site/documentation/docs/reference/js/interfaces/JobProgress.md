[**@inferedge/moss v1.0.0-beta.7**](../README.md)

***

[@inferedge/moss](../globals.md) / JobProgress

# Interface: JobProgress

Progress update passed to the `onProgress` callback during async operations.

## Properties

| Property | Type |
| ------ | ------ |
| <a id="property-jobid"></a> `jobId` | `string` |
| <a id="property-status"></a> `status` | [`JobStatus`](../type-aliases/JobStatus.md) |
| <a id="property-progress"></a> `progress` | `number` |
| <a id="property-currentphase"></a> `currentPhase` | [`JobPhase`](../type-aliases/JobPhase.md) \| `null` |

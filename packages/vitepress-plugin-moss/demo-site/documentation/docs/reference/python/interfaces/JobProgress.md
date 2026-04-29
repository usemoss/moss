---
title: "JobProgress (Python)"
---

[moss v1.0.0](../README.md)

[moss](../globals.md) / JobProgress

# Interface: JobProgress

<a id="interface-jobprogress"></a>

Progress update for a job.

## Properties

- **job_id**: `str`
- **status**: [`JobStatus`](JobStatus.md)
- **progress**: `float`
- **current_phase**: Optional[[`JobPhase`](JobPhase.md)]

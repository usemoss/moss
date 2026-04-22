---
title: "JobStatusResponse (Python)"
---

[moss v1.0.0](../README.md)

[moss](../globals.md) / JobStatusResponse

# Interface: JobStatusResponse

<a id="interface-jobstatusresponse"></a>

Full status response from get_job_status.

## Properties

- **job_id**: `str`
- **status**: [`JobStatus`](JobStatus.md)
- **progress**: `float`
- **current_phase**: Optional[[`JobPhase`](JobPhase.md)]
- **error**: `Optional[str]`
- **created_at**: `str`
- **updated_at**: `str`
- **completed_at**: `Optional[str]`

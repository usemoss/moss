---
title: "MossClient (Python)"
---

[moss v1.0.0](../README.md)

[moss](../globals.md) / MossClient

# Class: MossClient

<a id="class-mossclient"></a>

Semantic search client for vector similarity operations.

## Methods

### `create_index(name, docs, model_id)`

#### Parameters

- **name** (`str`)
- **docs** (List[[`DocumentInfo`](../interfaces/DocumentInfo.md)])
- **model_id** (`Optional[str]`)

#### Returns

[`MutationResult`](../interfaces/MutationResult.md)


---

### `add_docs(name, docs, options)`

#### Parameters

- **name** (`str`)
- **docs** (List[[`DocumentInfo`](../interfaces/DocumentInfo.md)])
- **options** (Optional[[`MutationOptions`](../interfaces/MutationOptions.md)] = `None`)

#### Returns

[`MutationResult`](../interfaces/MutationResult.md)


---

### `delete_docs(name, doc_ids)`

#### Parameters

- **name** (`str`)
- **doc_ids** (`List[str]`)

#### Returns

[`MutationResult`](../interfaces/MutationResult.md)


---

### `get_job_status(job_id)`

#### Parameters

- **job_id** (`str`)

#### Returns

[`JobStatusResponse`](../interfaces/JobStatusResponse.md)


---

### `get_index(name)`

#### Parameters

- **name** (`str`)

#### Returns

[`IndexInfo`](../interfaces/IndexInfo.md)


---

### `list_indexes()`

#### Returns

List[[`IndexInfo`](../interfaces/IndexInfo.md)]


---

### `delete_index(name)`

#### Parameters

- **name** (`str`)

#### Returns

`bool`


---

### `get_docs(name, options)`

#### Parameters

- **name** (`str`)
- **options** (Optional[[`GetDocumentsOptions`](../interfaces/GetDocumentsOptions.md)] = `None`)

#### Returns

List[[`DocumentInfo`](../interfaces/DocumentInfo.md)]


---

### `load_index(name, auto_refresh, polling_interval_in_seconds)`

#### Parameters

- **name** (`str`)
- **auto_refresh** (`bool` = `False`)
- **polling_interval_in_seconds** (`int` = `600`)

#### Returns

`str`


---

### `unload_index(name)`

#### Parameters

- **name** (`str`)


---

### `query(name, query, options, filter)`

#### Parameters

- **name** (`str`)
- **query** (`str`)
- **options** (Optional[[`QueryOptions`](../interfaces/QueryOptions.md)] = `None`)
- **filter** (`Optional[dict]` = `None`)

#### Returns

[`SearchResult`](../interfaces/SearchResult.md)


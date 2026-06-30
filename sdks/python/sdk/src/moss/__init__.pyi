from __future__ import annotations

from typing import ClassVar, Dict, List, Optional, Sequence, Tuple

class MossClient:
    """Semantic search client for vector similarity operations."""

    DEFAULT_MODEL_ID: ClassVar[str]

    def __init__(self, project_id: str, project_key: str) -> None: ...
    async def session(
        self,
        index_name: str,
        model_id: Optional[str] = None,
    ) -> SessionIndex: ...
    async def create_index(
        self,
        name: str,
        docs: List[DocumentInfo],
        model_id: Optional[str] = ...,
    ) -> MutationResult: ...
    async def create_index_from_files(
        self,
        name: str,
        files: List[ParseFileInput],
        model_id: Optional[str] = None,
    ) -> MutationResult: ...
    async def add_docs(
        self,
        name: str,
        docs: List[DocumentInfo],
        options: Optional[MutationOptions] = None,
    ) -> MutationResult: ...
    async def delete_docs(
        self,
        name: str,
        doc_ids: List[str],
    ) -> MutationResult: ...
    async def get_job_status(self, job_id: str) -> JobStatusResponse: ...
    async def get_index(self, name: str) -> IndexInfo: ...
    async def list_indexes(self) -> List[IndexInfo]: ...
    async def delete_index(self, name: str) -> bool: ...
    async def get_docs(
        self,
        name: str,
        options: Optional[GetDocumentsOptions] = None,
    ) -> List[DocumentInfo]: ...
    async def load_index(
        self,
        name: str,
        auto_refresh: bool = False,
        polling_interval_in_seconds: int = 600,
    ) -> str: ...
    async def unload_index(self, name: str) -> None: ...
    async def load_indexes(
        self,
        names: List[str],
        auto_refresh: bool = False,
        polling_interval_in_seconds: int = 600,
    ) -> LoadIndexesResult: ...
    async def unload_indexes(self, names: List[str]) -> None: ...
    async def query(
        self,
        name: str,
        query: str,
        options: Optional[QueryOptions] = None,
    ) -> SearchResult: ...
    async def query_multi_index(
        self,
        names: List[str],
        query: str,
        options: Optional[QueryOptions] = None,
    ) -> SearchResult: ...

class SessionIndex:
    """Local in-session index for real-time indexing and querying."""

    name: str
    doc_count: int

    async def add_docs(
        self,
        docs: List[DocumentInfo],
        options: Optional[MutationOptions] = None,
    ) -> Tuple[int, int]: ...
    async def delete_docs(self, doc_ids: List[str]) -> int: ...
    async def get_docs(
        self,
        options: Optional[GetDocumentsOptions] = None,
    ) -> List[DocumentInfo]: ...
    async def query(
        self,
        query: str,
        options: Optional[QueryOptions] = None,
    ) -> SearchResult: ...
    async def push_index(self) -> PushIndexResult: ...

class ParseFileInput:
    """Input descriptor for a single file in the parse pipeline."""

    name: str
    content_type: str
    path: Optional[str]
    data: Optional[bytes]

    def __init__(
        self,
        name: str,
        content_type: str,
        path: Optional[str] = None,
        data: Optional[bytes] = None,
    ) -> None: ...

class PushIndexResult:
    """Result from SessionIndex.push_index()."""

    job_id: str
    index_name: str
    doc_count: int
    status: str

class LoadIndexesResult:
    """Outcome of a load_indexes call. Best-effort across the batch."""

    loaded: List[str]
    failed: Dict[str, str]

    def __init__(
        self,
        loaded: Optional[List[str]] = None,
        failed: Optional[Dict[str, str]] = None,
    ) -> None: ...

class MutationResult:
    """Return value from create_index / add_docs / delete_docs."""

    job_id: str
    index_name: str
    doc_count: int

class MutationOptions:
    """Options for add_docs (e.g. upsert behavior)."""

    upsert: Optional[bool]

    def __init__(self, upsert: Optional[bool] = None) -> None: ...

class GetDocumentsOptions:
    """Options for get_docs (e.g. filter by document IDs)."""

    doc_ids: Optional[List[str]]

    def __init__(self, doc_ids: Optional[List[str]] = None) -> None: ...

class JobStatus:
    PENDING_UPLOAD: ClassVar[str]
    UPLOADING: ClassVar[str]
    BUILDING: ClassVar[str]
    COMPLETED: ClassVar[str]
    FAILED: ClassVar[str]

    value: str

class JobPhase:
    DOWNLOADING: ClassVar[str]
    DESERIALIZING: ClassVar[str]
    GENERATING_EMBEDDINGS: ClassVar[str]
    BUILDING_INDEX: ClassVar[str]
    UPLOADING: ClassVar[str]
    CLEANUP: ClassVar[str]

    value: str

class JobProgress:
    job_id: str
    status: JobStatus
    progress: float
    current_phase: Optional[JobPhase]

class JobStatusResponse:
    job_id: str
    status: JobStatus
    progress: float
    current_phase: Optional[JobPhase]
    error: Optional[str]
    created_at: str
    updated_at: str
    completed_at: Optional[str]

class ModelRef:
    id: str
    version: str
    def __init__(self, id: str, version: str) -> None: ...

class QueryResultDocumentInfo:
    id: str
    text: str
    metadata: Optional[Dict[str, str]]
    score: float
    index_name: Optional[str]
    def __init__(
        self,
        id: str,
        text: str,
        metadata: Optional[Dict[str, str]] = ...,
        score: float = ...,
        index_name: Optional[str] = ...,
    ) -> None: ...

class DocumentInfo:
    id: str
    text: str
    metadata: Optional[Dict[str, str]]
    embedding: Optional[Sequence[float]]
    def __init__(
        self,
        id: str,
        text: str,
        metadata: Optional[Dict[str, str]] = ...,
        embedding: Optional[Sequence[float]] = ...,
    ) -> None: ...

class QueryOptions:
    embedding: Optional[Sequence[float]]
    top_k: Optional[int]
    alpha: Optional[float]
    filter: Optional[dict]
    def __init__(
        self,
        embedding: Optional[Sequence[float]] = ...,
        top_k: Optional[int] = ...,
        alpha: Optional[float] = ...,
        filter: Optional[dict] = ...,
    ) -> None: ...

class IndexInfo:
    id: str
    name: str
    version: str
    status: str
    doc_count: int
    created_at: str
    updated_at: str
    model: ModelRef
    def __init__(
        self,
        id: str,
        name: str,
        version: str,
        status: str,
        doc_count: int,
        created_at: str,
        updated_at: str,
        model: ModelRef,
    ) -> None: ...

class SearchResult:
    docs: List[QueryResultDocumentInfo]
    query: str
    index_name: Optional[str]
    time_taken_ms: Optional[int]
    def __init__(
        self,
        docs: List[QueryResultDocumentInfo],
        query: str,
        index_name: Optional[str] = None,
        time_taken_ms: Optional[int] = None,
    ) -> None: ...

class IndexStatus:
    NotStarted: ClassVar[str]
    Building: ClassVar[str]
    Ready: ClassVar[str]
    Failed: ClassVar[str]
    def __init__(self, value: str) -> None: ...

IndexStatusValues: Dict[str, str]

__version__: str

__all__ = [
    "MossClient",
    "SessionIndex",
    "ParseFileInput",
    "PushIndexResult",
    "LoadIndexesResult",
    "DocumentInfo",
    "GetDocumentsOptions",
    "IndexInfo",
    "SearchResult",
    "QueryResultDocumentInfo",
    "ModelRef",
    "IndexStatus",
    "IndexStatusValues",
    "QueryOptions",
    "MutationResult",
    "MutationOptions",
    "JobStatus",
    "JobPhase",
    "JobProgress",
    "JobStatusResponse",
]

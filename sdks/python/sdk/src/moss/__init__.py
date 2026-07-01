"""
Moss Semantic Search SDK

Powerful Python SDK for semantic search using state-of-the-art embedding models.

Example:
    ```python
    from moss import MossClient, DocumentInfo

    client = MossClient('your-project-id', 'your-project-key')

    docs = [DocumentInfo(id="1", text="Example document")]

    result = await client.create_index('my-index', docs, 'moss-minilm')

    await client.load_index('my-index')
    results = await client.query('my-index', 'search query')
    ```

Local-first session indexing:
    ```python
    session = await client.session("call-abc123")

    await session.add_docs([DocumentInfo(id="1", text="Customer asked about billing")])
    results = await session.query("billing issue")

    result = await session.push_index()
    ```
"""

from moss_core import (
    DocumentInfo,
    GetDocumentsOptions,
    IndexInfo,
    IndexStatus,
    IndexStatusValues,
    LoadIndexesResult,
    ModelRef,
    MutationOptions,
    MutationResult,
    JobStatus,
    JobPhase,
    JobProgress,
    JobStatusResponse,
    PushIndexResult,
    QueryOptions,
    QueryResultDocumentInfo,
    SearchResult,
)

from .client.moss_client import MossClient, ParseFileInput
from .client.session_index import SessionIndex

__version__ = "1.4.1"

__all__ = [
    "MossClient",
    "ParseFileInput",
    "SessionIndex",
    "PushIndexResult",
    "LoadIndexesResult",
    # Core data types
    "DocumentInfo",
    "GetDocumentsOptions",
    "IndexInfo",
    "SearchResult",
    "QueryResultDocumentInfo",
    "ModelRef",
    "IndexStatus",
    "IndexStatusValues",
    "QueryOptions",
    # Mutation types
    "MutationResult",
    "MutationOptions",
    "JobStatus",
    "JobPhase",
    "JobProgress",
    "JobStatusResponse",
]

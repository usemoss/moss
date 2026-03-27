from typing import Any, Optional, Type
import asyncio
import uuid

from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from inferedge_moss import MossClient, QueryOptions, DocumentInfo


class MossSearchInput(BaseModel):
    query: str = Field(description="The search query text")


class MossSearchTool(BaseTool):
    """
    Semantic search tool powered by Moss.
    Wraps MossClient to provide sub-10ms semantic search as a CrewAI tool that agents can invoke.
    """

    name: str = "moss_search"
    description: str = (
        "Search a knowledge base using Moss semantic search. "
        "Returns the most relevant documents for a given query."
    )
    args_schema: Type[BaseModel] = MossSearchInput

    project_id: str = Field(description="Moss project ID")
    project_key: str = Field(description="Moss project key")
    index_name: str = Field(description="Name of the Moss index to search")
    top_k: int = Field(default=5, description="Number of results to return")
    alpha: float = Field(
        default=0.5,
        description="Hybrid search balance (0=keyword, 1=semantic)",
    )

    _client: Any = None
    _index_loaded: bool = False

    def model_post_init(self, __context: Any) -> None:
        self._client = MossClient(self.project_id, self.project_key)

    async def _ensure_loaded(self) -> None:
        if not self._index_loaded:
            await self._client.load_index(self.index_name)
            self._index_loaded = True

    def _run(self, query: str) -> str:
        """Synchronous search -- wraps the async implementation."""
        try:
            return asyncio.run(self._arun(query))
        except RuntimeError as e:
            if "cannot be called from a running event loop" in str(e):
                raise RuntimeError(
                    "MossSearchTool._run() cannot be called from a running event loop. "
                    "Use async mode or call from a standard script."
                ) from e
            raise

    async def _arun(self, query: str) -> str:
        """Async search against Moss index."""
        await self._ensure_loaded()
        results = await self._client.query(
            self.index_name,
            query,
            QueryOptions(top_k=self.top_k, alpha=self.alpha),
        )
        if not results.docs:
            return "No relevant information found."
        return "\n\n".join(
            f"Result {i+1} (score: {doc.score:.2f}):\n{doc.text}"
            for i, doc in enumerate(results.docs)
        )


class MossAddDocsInput(BaseModel):
    texts: list[str] = Field(description="List of text documents to add")
    ids: Optional[list[str]] = Field(
        default=None,
        description="Optional document IDs (auto-generated if omitted)",
    )


class MossAddDocsTool(BaseTool):
    """
    Tool for adding documents to a Moss index.
    Wraps MossClient.add_docs() so CrewAI agents can ingest new documents into a Moss search index.
    """

    name: str = "moss_add_docs"
    description: str = "Add text documents to a Moss semantic search index."
    args_schema: Type[BaseModel] = MossAddDocsInput

    project_id: str = Field(description="Moss project ID")
    project_key: str = Field(description="Moss project key")
    index_name: str = Field(description="Name of the Moss index")

    _client: Any = None

    def model_post_init(self, __context: Any) -> None:
        self._client = MossClient(self.project_id, self.project_key)

    def _run(self, texts: list[str], ids: Optional[list[str]] = None) -> str:
        """Synchronous add docs -- wraps the async implementation."""
        try:
            return asyncio.run(self._arun(texts, ids))
        except RuntimeError as e:
            if "cannot be called from a running event loop" in str(e):
                raise RuntimeError(
                    "MossAddDocsTool._run() cannot be called from a running event loop. "
                    "Use async mode or call from a standard script."
                ) from e
            raise

    async def _arun(self, texts: list[str], ids: Optional[list[str]] = None) -> str:
        """Async add documents to Moss index."""
        docs = [
            DocumentInfo(
                id=ids[i] if ids and i < len(ids) else str(uuid.uuid4()),
                text=text,
            )
            for i, text in enumerate(texts)
        ]
        await self._client.add_docs(self.index_name, docs)
        return f"Successfully added {len(docs)} documents."


class MossDeleteDocsInput(BaseModel):
    doc_ids: list[str] = Field(description="List of document IDs to delete")


class MossDeleteDocsTool(BaseTool):
    """Delete documents from a Moss index by their IDs."""

    name: str = "moss_delete_docs"
    description: str = "Delete specific documents from a Moss index by their IDs."
    args_schema: Type[BaseModel] = MossDeleteDocsInput

    project_id: str = Field(description="Moss project ID")
    project_key: str = Field(description="Moss project key")
    index_name: str = Field(description="Name of the Moss index")

    _client: Any = None

    def model_post_init(self, __context: Any) -> None:
        self._client = MossClient(self.project_id, self.project_key)

    def _run(self, doc_ids: list[str]) -> str:
        try:
            return asyncio.run(self._arun(doc_ids))
        except RuntimeError as e:
            if "cannot be called from a running event loop" in str(e):
                raise RuntimeError(
                    "MossDeleteDocsTool._run() cannot be called from a running event loop."
                ) from e
            raise

    async def _arun(self, doc_ids: list[str]) -> str:
        await self._client.delete_docs(self.index_name, doc_ids)
        return f"Successfully deleted {len(doc_ids)} documents."


class MossListIndexesInput(BaseModel):
    pass  # No input needed


class MossListIndexesTool(BaseTool):
    """List all available Moss indexes."""

    name: str = "moss_list_indexes"
    description: str = "List all available indexes in the Moss project with their details."
    args_schema: Type[BaseModel] = MossListIndexesInput

    project_id: str = Field(description="Moss project ID")
    project_key: str = Field(description="Moss project key")

    _client: Any = None

    def model_post_init(self, __context: Any) -> None:
        self._client = MossClient(self.project_id, self.project_key)

    def _run(self) -> str:
        try:
            return asyncio.run(self._arun())
        except RuntimeError as e:
            if "cannot be called from a running event loop" in str(e):
                raise RuntimeError(
                    "MossListIndexesTool._run() cannot be called from a running event loop."
                ) from e
            raise

    async def _arun(self) -> str:
        indexes = await self._client.list_indexes()
        if not indexes:
            return "No indexes found."
        lines = []
        for idx in indexes:
            name = getattr(idx, "name", "unknown")
            doc_count = getattr(idx, "doc_count", "?")
            status = getattr(idx, "status", "?")
            lines.append(f"- {name} ({doc_count} docs, status: {status})")
        return "Indexes:\n" + "\n".join(lines)


class MossGetDocsInput(BaseModel):
    doc_ids: Optional[list[str]] = Field(
        default=None,
        description="Optional list of document IDs to retrieve. If omitted, returns all documents.",
    )


class MossGetDocsTool(BaseTool):
    """Retrieve documents from a Moss index."""

    name: str = "moss_get_docs"
    description: str = (
        "Retrieve documents from a Moss index. "
        "Can fetch specific documents by ID or all documents."
    )
    args_schema: Type[BaseModel] = MossGetDocsInput

    project_id: str = Field(description="Moss project ID")
    project_key: str = Field(description="Moss project key")
    index_name: str = Field(description="Name of the Moss index")

    _client: Any = None

    def model_post_init(self, __context: Any) -> None:
        self._client = MossClient(self.project_id, self.project_key)

    def _run(self, doc_ids: Optional[list[str]] = None) -> str:
        try:
            return asyncio.run(self._arun(doc_ids))
        except RuntimeError as e:
            if "cannot be called from a running event loop" in str(e):
                raise RuntimeError(
                    "MossGetDocsTool._run() cannot be called from a running event loop."
                ) from e
            raise

    async def _arun(self, doc_ids: Optional[list[str]] = None) -> str:
        from inferedge_moss import GetDocumentsOptions

        options = None
        if doc_ids:
            options = GetDocumentsOptions(doc_ids=doc_ids)
        docs = await self._client.get_docs(self.index_name, options)
        if not docs:
            return "No documents found."
        lines = []
        for doc in docs:
            text_preview = doc.text[:150] + "..." if len(doc.text) > 150 else doc.text
            lines.append(f"[{doc.id}] {text_preview}")
        return f"Retrieved {len(docs)} documents:\n" + "\n".join(lines)


class MossCreateIndexInput(BaseModel):
    index_name: str = Field(description="Name for the new index")
    texts: list[str] = Field(description="List of text documents to index")
    ids: Optional[list[str]] = Field(
        default=None,
        description="Optional document IDs (auto-generated if omitted)",
    )


class MossCreateIndexTool(BaseTool):
    """Create a new Moss index with documents."""

    name: str = "moss_create_index"
    description: str = (
        "Create a new Moss semantic search index and populate it with documents."
    )
    args_schema: Type[BaseModel] = MossCreateIndexInput

    project_id: str = Field(description="Moss project ID")
    project_key: str = Field(description="Moss project key")

    _client: Any = None

    def model_post_init(self, __context: Any) -> None:
        self._client = MossClient(self.project_id, self.project_key)

    def _run(self, index_name: str, texts: list[str], ids: Optional[list[str]] = None) -> str:
        try:
            return asyncio.run(self._arun(index_name, texts, ids))
        except RuntimeError as e:
            if "cannot be called from a running event loop" in str(e):
                raise RuntimeError(
                    "MossCreateIndexTool._run() cannot be called from a running event loop."
                ) from e
            raise

    async def _arun(self, index_name: str, texts: list[str], ids: Optional[list[str]] = None) -> str:
        docs = [
            DocumentInfo(
                id=ids[i] if ids and i < len(ids) else str(uuid.uuid4()),
                text=text,
            )
            for i, text in enumerate(texts)
        ]
        await self._client.create_index(index_name, docs)
        return f"Successfully created index '{index_name}' with {len(docs)} documents."


class MossDeleteIndexInput(BaseModel):
    index_name: str = Field(description="Name of the index to delete")


class MossDeleteIndexTool(BaseTool):
    """Delete a Moss index and all its data."""

    name: str = "moss_delete_index"
    description: str = "Delete a Moss index and all its documents. This action is irreversible."
    args_schema: Type[BaseModel] = MossDeleteIndexInput

    project_id: str = Field(description="Moss project ID")
    project_key: str = Field(description="Moss project key")

    _client: Any = None

    def model_post_init(self, __context: Any) -> None:
        self._client = MossClient(self.project_id, self.project_key)

    def _run(self, index_name: str) -> str:
        try:
            return asyncio.run(self._arun(index_name))
        except RuntimeError as e:
            if "cannot be called from a running event loop" in str(e):
                raise RuntimeError(
                    "MossDeleteIndexTool._run() cannot be called from a running event loop."
                ) from e
            raise

    async def _arun(self, index_name: str) -> str:
        await self._client.delete_index(index_name)
        return f"Successfully deleted index '{index_name}'."


def moss_tools(
    project_id: str,
    project_key: str,
    index_name: str,
    top_k: int = 5,
    alpha: float = 0.5,
) -> list[BaseTool]:
    """Create all Moss tools with shared configuration.

    Returns: [search, add_docs, delete_docs, get_docs, list_indexes,
              create_index, delete_index]
    """
    creds = dict(project_id=project_id, project_key=project_key)
    index_kwargs = dict(**creds, index_name=index_name)
    return [
        MossSearchTool(**index_kwargs, top_k=top_k, alpha=alpha),
        MossAddDocsTool(**index_kwargs),
        MossDeleteDocsTool(**index_kwargs),
        MossGetDocsTool(**index_kwargs),
        MossListIndexesTool(**creds),
        MossCreateIndexTool(**creds),
        MossDeleteIndexTool(**creds),
    ]

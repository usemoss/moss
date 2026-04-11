"""MossSink -- writes batches of SourceDocuments into a Moss index."""

from __future__ import annotations

from typing import List, Optional

from moss import DocumentInfo, MossClient

from .adapters.base import SourceDocument, SourcePreview


class MossSink:
    """Converts SourceDocuments to Moss DocumentInfo and writes them."""

    def __init__(
        self,
        client: MossClient,
        index_name: str,
        re_embed: bool,
        model: Optional[str],
    ) -> None:
        self._client = client
        self._index_name = index_name
        self._re_embed = re_embed
        self._model = model or "moss-minilm"

    async def ensure_index(self, preview: SourcePreview) -> None:
        """Create the target index if it does not already exist.

        Uses model_id="custom" only when preserving existing embeddings
        AND the source actually has embeddings.  Otherwise uses the
        configured model so Moss generates embeddings.
        """
        try:
            await self._client.get_index(self._index_name)
        except Exception:
            # Index doesn't exist -- create with an empty initial doc set.
            has_embeddings = preview.dimensions is not None and not self._re_embed
            model = "custom" if has_embeddings else self._model
            placeholder = [DocumentInfo(id="__init__", text="placeholder")]
            await self._client.create_index(
                self._index_name, placeholder, model
            )
            # Clean up the placeholder after index is ready
            try:
                await self._client.delete_docs(self._index_name, ["__init__"])
            except Exception:
                pass  # best-effort cleanup

    async def write_batch(self, docs: List[SourceDocument]) -> str:
        """Write a batch of documents to the target index.

        Returns the job_id from the mutation result.
        """
        moss_docs = [self._convert(d) for d in docs]
        from moss import MutationOptions

        result = await self._client.add_docs(
            self._index_name,
            moss_docs,
            MutationOptions(upsert=True),
        )
        return result.job_id

    def _convert(self, doc: SourceDocument) -> DocumentInfo:
        """Convert a SourceDocument to a Moss DocumentInfo."""
        embedding = None
        if not self._re_embed and doc.embedding is not None:
            embedding = doc.embedding
        # When re_embed=True we drop the embedding so Moss generates one.
        return DocumentInfo(
            id=doc.id,
            text=doc.text,
            metadata=doc.metadata,
            embedding=embedding,
        )

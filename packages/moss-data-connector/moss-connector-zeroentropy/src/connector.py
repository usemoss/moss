from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

from moss import DocumentInfo
from zeroentropy import ZeroEntropy


def coerce_metadata(metadata: dict[str, Any] | None) -> dict[str, str]:
    """Coerce ZeroEntropy metadata into what Moss accepts.

    ZeroEntropy metadata values are ``str | list[str]``; ``DocumentInfo.metadata``
    requires ``dict[str, str]``. List values are joined with ", "; anything else
    is stringified.
    """
    coerced: dict[str, str] = {}
    for key, value in (metadata or {}).items():
        coerced[key] = ", ".join(value) if isinstance(value, list) else str(value)
    return coerced


def default_mapper(row: dict[str, Any]) -> DocumentInfo:
    """Canonical ZeroEntropy -> Moss mapping.

    Uses the document ``path`` as the Moss id, the fetched ``content`` as the
    searchable text, and copies ``metadata`` (list values joined into strings).
    Pass your own ``mapper`` to ``ZeroEntropyConnector`` to override.
    """
    return DocumentInfo(
        id=row["path"],
        text=row.get("content") or "",
        metadata=coerce_metadata(row.get("metadata")),
    )


class ZeroEntropyConnector:
    """Read documents from a ZeroEntropy collection and yield Moss ``DocumentInfo``.

    Each ZeroEntropy document becomes one row dict (its get-document-info fields
    plus the fetched ``content``) passed to ``mapper``. The default mapper does
    the canonical migration (path -> id, content -> text, metadata -> metadata),
    so copying a whole collection into Moss needs no mapper.

    Args:
        collection_name: The ZeroEntropy collection to read from.
        mapper: Turns one row dict into a ``DocumentInfo``. Defaults to
            ``default_mapper``.
        api_key: ZeroEntropy API key. When ``None`` the SDK falls back to the
            ``ZEROENTROPY_API_KEY`` environment variable.
        path_prefix: Only migrate documents whose path starts with this prefix.
        include_content: When ``True`` (default) each document's parsed text is
            fetched via ``get_info(..., include_content=True)`` and put on the
            row as ``content``; documents with no content are skipped. Set
            ``False`` to migrate metadata only (your ``mapper`` must not rely on
            ``content``).
    """

    def __init__(
        self,
        collection_name: str,
        mapper: Callable[[dict[str, Any]], DocumentInfo] = default_mapper,
        *,
        api_key: str | None = None,
        path_prefix: str | None = None,
        include_content: bool = True,
    ) -> None:
        # The default mapper reads `content`, so turning it off would silently
        # produce empty-text documents. Fail fast: opting out of content fetch
        # only makes sense with a custom mapper that does not use `content`.
        if not include_content and mapper is default_mapper:
            raise ValueError(
                "include_content=False with the default mapper would index empty "
                "documents. Pass a custom mapper that does not read 'content', or "
                "leave include_content=True."
            )

        self.collection_name = collection_name
        self.mapper = mapper
        self.api_key = api_key
        self.path_prefix = path_prefix
        self.include_content = include_content

    def __iter__(self) -> Iterator[DocumentInfo]:
        client = ZeroEntropy(api_key=self.api_key)

        list_kwargs: dict[str, Any] = {"collection_name": self.collection_name}
        if self.path_prefix is not None:
            list_kwargs["path_prefix"] = self.path_prefix

        # get_info_list is an auto-paginating cursor: iterating walks every page.
        for doc in client.documents.get_info_list(**list_kwargs):
            row: dict[str, Any] = {
                "id": doc.id,
                "path": doc.path,
                "metadata": doc.metadata,
                "file_url": doc.file_url,
                "index_status": doc.index_status,
                "num_pages": doc.num_pages,
                "size": doc.size,
            }
            if self.include_content:
                # The list endpoint never returns text; fetch it per document.
                info = client.documents.get_info(
                    collection_name=self.collection_name,
                    path=doc.path,
                    include_content=True,
                )
                content = info.document.content
                # A document that never parsed (parsing_failed, still parsing,
                # etc.) has no text to migrate; skip it rather than indexing an
                # empty document into Moss.
                if not content:
                    continue
                row["content"] = content
            yield self.mapper(row)

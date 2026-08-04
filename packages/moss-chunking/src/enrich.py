"""Optional post-steps that rewrite a chunk's text after it is cut.

These are retrieval-quality tricks, not splitting tricks, so they live outside
`ChunkingStrategy` and compose with any of them. Keeping them separate is also
what makes them adoptable: pikachu already does the trick below by hand, and it
would keep its own copy if the only way to get it were to switch splitters.
"""

from __future__ import annotations

from collections.abc import Mapping

from moss import DocumentInfo


def prepend_context(doc: DocumentInfo, fields: Mapping[str, str]) -> DocumentInfo:
    """Return `doc` with `fields` written into the top of its text.

    Moss's hybrid search scores BM25 over chunk text, so facts that live only in
    metadata — the filename, the folder it sits in — are invisible to the keyword
    half of the query. Restating them in the text makes them matchable. This is
    pikachu's `enrich_chunk_body`, generalised: it prepends `Filename:` and
    `Path:` so a search for a file by name finds it.

    The ID and metadata are untouched, so an enriched chunk is still addressable
    exactly as the contract says it is.
    """
    if not fields:
        return doc
    header = "\n".join(f"{key}: {value}" for key, value in fields.items())
    return DocumentInfo(
        id=doc.id,
        text=f"{header}\n\n{doc.text}",
        metadata=doc.metadata,
        embedding=getattr(doc, "embedding", None),
    )


def prepend_source_context(doc: DocumentInfo, filename: str, path: str) -> DocumentInfo:
    """`prepend_context` with pikachu's exact field set, for file-backed chunks."""
    return prepend_context(doc, {"Filename": filename, "Path": path})

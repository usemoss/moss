"""Build DocumentInfo lists from a resolved repository root."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from moss import DocumentInfo

from .chunkers import FileChunkRequest, chunk_code, chunk_markdown
from .discover import discover_files
from .language import is_markdown_path, language_for_path
from .types import IndexOptions


def build_documents(root: Path, options: Optional[IndexOptions] = None) -> List[DocumentInfo]:
    """Discover files under `root`, chunk them, and return DocumentInfo rows."""
    opts = options or IndexOptions()
    documents: List[DocumentInfo] = []
    for path in discover_files(root, opts):
        documents.extend(_chunk_file(path, root, opts))
    return documents


def _chunk_file(path: Path, root: Path, options: IndexOptions) -> List[DocumentInfo]:
    content = _read_text(path)
    if content is None:
        return []
    request = FileChunkRequest(
        path=path,
        root=root,
        content=content,
        language=language_for_path(path),
        repo_name=options.repo_name,
        ref=options.ref,
    )
    if is_markdown_path(path):
        return chunk_markdown(request)
    return chunk_code(request)


def _read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

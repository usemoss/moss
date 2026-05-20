"""Helpers for indexing source files into Moss.

This module stays intentionally small: one source file becomes one Moss
document, with path and symbol metadata attached for agent prompts.
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any, Iterable, Iterator, List

SOURCE_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".go",
    ".h",
    ".hpp",
    ".java",
    ".js",
    ".jsx",
    ".json",
    ".md",
    ".py",
    ".rs",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}

IGNORED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}


def iter_source_files(project_root: str | Path) -> Iterator[Path]:
    """Yield text source files that are useful for semantic code search."""
    root = Path(project_root)
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SOURCE_EXTENSIONS:
            continue
        if any(part in IGNORED_DIRS for part in path.relative_to(root).parts):
            continue
        yield path


def extract_python_symbols(source: str) -> List[str]:
    """Return top-level Python classes and functions from a source string."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    symbols: List[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.append(node.name)
    return symbols


def _language_for(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    return {
        "md": "markdown",
        "py": "python",
        "toml": "toml",
        "ts": "typescript",
        "tsx": "typescript",
        "js": "javascript",
        "jsx": "javascript",
        "yml": "yaml",
    }.get(suffix, suffix or "text")


def _document_text(relative_path: str, content: str, max_file_chars: int) -> str:
    truncated = len(content) > max_file_chars
    body = content[:max_file_chars]
    if truncated:
        body = f"{body}\n\n[truncated]"
    return f"Path: {relative_path}\n\n```text\n{body}\n```"


def build_code_documents(
    project_root: str | Path,
    *,
    max_file_chars: int = 12_000,
) -> List[Any]:
    """Build Moss DocumentInfo objects for a local project tree."""
    from moss import DocumentInfo

    root = Path(project_root)
    documents: List[Any] = []
    for path in iter_source_files(root):
        relative_path = path.relative_to(root).as_posix()
        content = path.read_text(encoding="utf-8")
        digest = hashlib.sha1(content.encode("utf-8")).hexdigest()[:12]
        symbols = extract_python_symbols(content) if path.suffix == ".py" else []
        documents.append(
            DocumentInfo(
                id=f"{relative_path}::{digest}",
                text=_document_text(relative_path, content, max_file_chars),
                metadata={
                    "path": relative_path,
                    "language": _language_for(path),
                    "symbols": ", ".join(symbols),
                },
            )
        )
    return documents


async def search_code(
    client: Any,
    index_name: str,
    query: str,
    *,
    top_k: int = 6,
    alpha: float = 0.75,
) -> List[Any]:
    """Query Moss for code context relevant to a bug report or task."""
    from moss import QueryOptions

    results = await client.query(
        index_name, query, QueryOptions(top_k=top_k, alpha=alpha)
    )
    return list(results.docs)


def format_search_results(docs: Iterable[Any]) -> str:
    """Format Moss hits for an LLM prompt."""
    blocks: List[str] = []
    for index, doc in enumerate(docs, 1):
        metadata = getattr(doc, "metadata", {}) or {}
        path = metadata.get("path") or getattr(doc, "id", "unknown")
        score = getattr(doc, "score", None)
        score_text = f" score={score:.3f}" if isinstance(score, (float, int)) else ""
        symbols = metadata.get("symbols")
        symbol_text = f" symbols={symbols}" if symbols else ""
        blocks.append(
            f"Result {index}: {path}{score_text}{symbol_text}\n"
            f"{getattr(doc, 'text', '')}"
        )
    return "\n\n---\n\n".join(blocks)

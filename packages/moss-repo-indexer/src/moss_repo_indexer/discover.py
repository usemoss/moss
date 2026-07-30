"""Walk a repository root and yield files to index."""

from __future__ import annotations

import fnmatch
import subprocess
from pathlib import Path
from typing import Iterable, List, Optional, Set

from .types import IndexOptions


def discover_files(root: Path, options: IndexOptions) -> List[Path]:
    """Return absolute paths of files that should be chunked."""
    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Repository root is not a directory: {root}")

    candidates = _list_candidates(root, options)
    matched = [path for path in candidates if _matches_include(path, root, options.include_globs)]
    sized = [path for path in matched if _within_size_limit(path, options.max_file_bytes)]
    return sorted(sized)


def _list_candidates(root: Path, options: IndexOptions) -> List[Path]:
    if options.respect_gitignore and _is_git_repo(root):
        tracked = _git_tracked_files(root)
        if tracked is not None:
            return tracked
    return _walk_filesystem(root, set(options.exclude_dirs))


def _is_git_repo(root: Path) -> bool:
    return (root / ".git").exists()


def _git_tracked_files(root: Path) -> Optional[List[Path]]:
    if subprocess.run(["git", "--version"], capture_output=True, check=False).returncode != 0:
        return None
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    rel_paths = [p for p in result.stdout.decode("utf-8", errors="replace").split("\0") if p]
    files: List[Path] = []
    for rel in rel_paths:
        path = root / rel
        if path.is_file():
            files.append(path)
    return files


def _walk_filesystem(root: Path, exclude_dirs: Set[str]) -> List[Path]:
    files: List[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if _is_under_excluded_dir(path, root, exclude_dirs):
            continue
        files.append(path)
    return files


def _is_under_excluded_dir(path: Path, root: Path, exclude_dirs: Set[str]) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return True
    return any(part in exclude_dirs for part in parts[:-1])


def _matches_include(path: Path, root: Path, include_globs: Iterable[str]) -> bool:
    rel = path.relative_to(root).as_posix()
    name = path.name
    for pattern in include_globs:
        if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(name, pattern):
            return True
        # fnmatch treats "**/*.md" as requiring a slash; allow root-level matches.
        if pattern.startswith("**/") and fnmatch.fnmatch(name, pattern[3:]):
            return True
    return False


def _within_size_limit(path: Path, max_file_bytes: int) -> bool:
    try:
        return path.stat().st_size <= max_file_bytes
    except OSError:
        return False

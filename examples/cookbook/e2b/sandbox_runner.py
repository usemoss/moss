"""E2B sandbox helpers for validating candidate code patches."""

from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, List

from code_index import IGNORED_DIRS

DEFAULT_SANDBOX_ROOT = "/home/user/moss-e2b-workspace"
_EXIT_SENTINEL = "__MOSS_COMMAND_EXIT_CODE__="
MAX_PROJECT_FILE_BYTES = 2_000_000
IGNORED_FILE_NAMES = {".env"}


@dataclass(frozen=True)
class PatchFile:
    """A complete file replacement proposed by the coding agent."""

    path: str
    content: str


@dataclass(frozen=True)
class ProposedPatch:
    """Structured patch response returned by the LLM."""

    summary: str
    files: List[PatchFile]


@dataclass(frozen=True)
class CommandOutput:
    """A command result normalized across E2B SDK behavior."""

    command: str
    exit_code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


async def create_e2b_sandbox(timeout: int = 600) -> Any:
    """Create an E2B sandbox.

    The E2B SDK reads E2B_API_KEY from the environment.
    """
    from e2b import AsyncSandbox

    return await AsyncSandbox.create(
        timeout=timeout,
        metadata={"cookbook": "moss-e2b-code-agent"},
    )


def sandbox_identifier(sandbox: Any) -> str:
    """Return a useful sandbox identifier for logs."""
    return (
        getattr(sandbox, "sandbox_id", None)
        or getattr(sandbox, "id", None)
        or "unknown"
    )


def _validate_relative_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip()
    if not normalized:
        raise ValueError("Patch path cannot be empty.")

    posix_path = PurePosixPath(normalized)
    if posix_path.is_absolute() or any(part in {"", ".."} for part in posix_path.parts):
        raise ValueError(f"Unsafe patch path: {path}")
    return posix_path.as_posix()


def _sandbox_path(root: str, relative_path: str) -> str:
    return (PurePosixPath(root) / _validate_relative_path(relative_path)).as_posix()


def _is_ignored_project_file(root: Path, path: Path) -> bool:
    relative = path.relative_to(root)
    if any(part in IGNORED_DIRS for part in relative.parts):
        return True
    if path.name in IGNORED_FILE_NAMES or path.name.startswith(".env."):
        return True
    return path.stat().st_size > MAX_PROJECT_FILE_BYTES


def iter_project_files(local_root: str | Path) -> Iterable[Path]:
    """Yield project files that should be copied into the sandbox."""
    root = Path(local_root)
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if _is_ignored_project_file(root, path):
            continue
        yield path


async def write_project_to_sandbox(
    sandbox: Any,
    local_root: str | Path,
    sandbox_root: str = DEFAULT_SANDBOX_ROOT,
) -> int:
    """Copy runnable project files from a local project into an E2B sandbox."""
    root = Path(local_root)
    count = 0
    for path in iter_project_files(root):
        relative_path = path.relative_to(root).as_posix()
        await sandbox.files.write(
            _sandbox_path(sandbox_root, relative_path),
            path.read_bytes(),
        )
        count += 1
    return count


def _looks_like_test_path(path: str) -> bool:
    posix_path = PurePosixPath(path.replace("\\", "/"))
    parts = [part.lower() for part in posix_path.parts]
    name = posix_path.name.lower()
    return "tests" in parts or name.startswith("test_") or name.endswith("_test.py")


def ensure_source_patch_only(files: Iterable[PatchFile]) -> List[PatchFile]:
    """Reject patch files that target tests, preserving validation integrity."""
    patch_files = list(files)
    test_paths = [
        patch_file.path
        for patch_file in patch_files
        if _looks_like_test_path(patch_file.path)
    ]
    if test_paths:
        joined = ", ".join(test_paths)
        raise ValueError(f"Refusing to apply patches to test files: {joined}")
    return patch_files


async def apply_patch_files(
    sandbox: Any,
    files: Iterable[PatchFile],
    sandbox_root: str = DEFAULT_SANDBOX_ROOT,
) -> int:
    """Apply complete file replacements inside the sandbox."""
    count = 0
    for patch_file in files:
        await sandbox.files.write(
            _sandbox_path(sandbox_root, patch_file.path),
            patch_file.content,
        )
        count += 1
    return count


def _wrapped_shell_command(command: str) -> str:
    script = (
        "set +e\n"
        "(\n"
        f"{command}\n"
        ")\n"
        "code=$?\n"
        f"printf '\\n{_EXIT_SENTINEL}%s\\n' \"$code\"\n"
        "exit 0\n"
    )
    return f"bash -lc {shlex.quote(script)}"


def _parse_wrapped_exit_code(stdout: str, fallback: int | None) -> tuple[int, str]:
    match = re.search(rf"\n?{re.escape(_EXIT_SENTINEL)}(-?\d+)\s*$", stdout)
    if not match:
        return (0 if fallback is None else int(fallback), stdout)
    exit_code = int(match.group(1))
    clean_stdout = stdout[: match.start()].rstrip()
    return exit_code, clean_stdout


async def run_sandbox_command(
    sandbox: Any,
    command: str,
    *,
    cwd: str = DEFAULT_SANDBOX_ROOT,
    timeout: float = 120,
) -> CommandOutput:
    """Run a command in E2B and preserve non-zero exit codes as data."""
    result = await sandbox.commands.run(
        _wrapped_shell_command(command),
        cwd=cwd,
        timeout=timeout,
    )
    raw_stdout = getattr(result, "stdout", "") or ""
    stderr = getattr(result, "stderr", "") or ""
    fallback_exit_code = getattr(result, "exit_code", None)
    exit_code, stdout = _parse_wrapped_exit_code(raw_stdout, fallback_exit_code)
    return CommandOutput(
        command=command, exit_code=exit_code, stdout=stdout, stderr=stderr
    )


async def run_tests(
    sandbox: Any,
    *,
    command: str = "python -m pytest -q",
    cwd: str = DEFAULT_SANDBOX_ROOT,
    timeout: float = 120,
) -> CommandOutput:
    """Run the project test command in the sandbox."""
    return await run_sandbox_command(sandbox, command, cwd=cwd, timeout=timeout)


def _extract_json_object(raw: str) -> str:
    fenced = re.search(r"```(?:json)?\s*(.*?)```", raw, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        return fenced.group(1).strip()

    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("LLM response did not contain a JSON object.")
    return raw[start : end + 1]


def parse_patch_json(raw: str) -> ProposedPatch:
    """Parse the LLM JSON patch format used by the cookbook."""
    data = json.loads(_extract_json_object(raw))
    files_data = data.get("files")
    if not isinstance(files_data, list) or not files_data:
        raise ValueError("Patch JSON must include a non-empty 'files' list.")

    files: List[PatchFile] = []
    for item in files_data:
        if not isinstance(item, dict):
            raise ValueError("Each patch file must be an object.")
        path = item.get("path")
        content = item.get("content")
        content_lines = item.get("content_lines")
        if isinstance(content_lines, list) and all(
            isinstance(line, str) for line in content_lines
        ):
            content = "\n".join(content_lines) + "\n"
        if not isinstance(path, str) or not isinstance(content, str):
            raise ValueError(
                "Each patch file needs string 'path' and either string "
                "'content' or string-list 'content_lines'."
            )
        files.append(PatchFile(path=_validate_relative_path(path), content=content))

    return ProposedPatch(summary=str(data.get("summary", "")).strip(), files=files)

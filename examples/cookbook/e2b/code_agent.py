"""Self-healing code agent powered by Moss search and E2B validation."""

from __future__ import annotations

import argparse
import asyncio
import os
import shlex
import sys
import textwrap
import uuid
from pathlib import Path
from typing import Any, List

from code_index import build_code_documents, format_search_results, search_code
from sandbox_runner import (
    DEFAULT_SANDBOX_ROOT,
    CommandOutput,
    ProposedPatch,
    apply_patch_files,
    create_e2b_sandbox,
    ensure_source_patch_only,
    parse_patch_json,
    run_sandbox_command,
    run_tests,
    sandbox_identifier,
    write_project_to_sandbox,
)

SAMPLE_PROJECT = Path(__file__).parent / "sample_project"
DEFAULT_REUSABLE_INDEX_NAME = "moss-e2b-code-agent"
DEFAULT_ISSUE = (
    "Checkout totals are too low when tax_rate is a decimal rate such as 0.0825. "
    "Tax should be calculated from the subtotal, not added as a flat amount."
)


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def _require_env(names: List[str]) -> None:
    missing = [name for name in names if not os.getenv(name)]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(f"Missing required environment variables: {joined}")


def _default_index_name() -> str:
    return f"e2b-code-agent-{uuid.uuid4().hex[:8]}"


def _resolve_index_name(args: argparse.Namespace) -> str:
    configured_name = args.index_name or os.getenv("MOSS_INDEX_NAME")
    if configured_name:
        return configured_name
    if args.reuse_index:
        return DEFAULT_REUSABLE_INDEX_NAME
    return _default_index_name()


async def _create_moss_index(client: Any, project_root: Path, index_name: str) -> None:
    documents = build_code_documents(project_root)
    if not documents:
        raise ValueError(f"No indexable source files found in {project_root}")

    print(f"Indexing {len(documents)} source files in Moss (index: {index_name})...")
    result = await client.create_index(index_name, documents)
    print(f"Index ready (job_id: {result.job_id})")
    await client.load_index(index_name)


async def _prepare_moss_index(
    project_root: Path,
    index_name: str,
    *,
    reuse_index: bool,
) -> tuple[Any, bool]:
    from moss import MossClient

    client = MossClient(os.environ["MOSS_PROJECT_ID"], os.environ["MOSS_PROJECT_KEY"])

    if reuse_index:
        try:
            print(f"Loading existing Moss index '{index_name}'...")
            await client.load_index(index_name)
            print("Reusing Moss index.")
            return client, False
        except RuntimeError:
            print("Reusable Moss index not found; creating it...")

    await _create_moss_index(client, project_root, index_name)
    return client, True


async def _propose_patch(issue: str, context: str, model: str) -> ProposedPatch:
    from groq import AsyncGroq

    client = AsyncGroq()
    system = (
        "You are a senior Python engineer fixing a small failing codebase. "
        "Use the retrieved Moss context to make a minimal source-code fix. "
        "Do not modify tests. Preserve existing formatting, imports, comments, "
        "and quote style unless a change is required for the fix. Return only "
        "valid JSON. Do not use markdown, triple-quoted strings, or raw "
        "multiline JSON strings. Use this schema: "
        '{"summary": "short summary", "files": [{"path": "relative/path.py", '
        '"content_lines": ["first line", "second line"]}]}. '
        "Each content_lines item must be exactly one source line without a "
        "trailing newline."
    )
    user = (
        f"Issue:\n{issue}\n\n"
        "Relevant code retrieved by Moss:\n"
        f"{context}\n\n"
        "Return complete replacement contents for only the files that must change. "
        "Keep the patch as small as possible. Represent file contents as "
        "content_lines arrays."
    )
    response = await client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    content = response.choices[0].message.content or ""
    return parse_patch_json(content)


def _git_pathspec(files: List[Any]) -> str:
    return " ".join(shlex.quote(patch_file.path) for patch_file in files)


def _print_command(label: str, output: CommandOutput) -> None:
    status = "passed" if output.ok else f"failed (exit {output.exit_code})"
    print(f"\n{label}: {status}")
    if output.stdout.strip():
        print(textwrap.indent(output.stdout.strip(), "  "))
    if output.stderr.strip():
        print(textwrap.indent(output.stderr.strip(), "  "))


async def run_code_repair(args: argparse.Namespace) -> bool:
    _load_dotenv()
    _require_env(["MOSS_PROJECT_ID", "MOSS_PROJECT_KEY", "E2B_API_KEY", "GROQ_API_KEY"])

    project_root = Path(args.project_root).resolve()
    index_name = _resolve_index_name(args)
    issue = args.issue or DEFAULT_ISSUE
    model = args.model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    moss_client = None
    sandbox = None
    created_index = False

    try:
        moss_client, created_index = await _prepare_moss_index(
            project_root,
            index_name,
            reuse_index=args.reuse_index,
        )

        hits = await search_code(
            moss_client,
            index_name,
            issue,
            top_k=args.top_k,
            alpha=args.alpha,
        )
        context = format_search_results(hits)
        paths = [
            (getattr(hit, "metadata", {}) or {}).get("path", hit.id) for hit in hits
        ]
        print("\nMoss retrieved:")
        for path in paths:
            print(f"  - {path}")

        print(f"\nAsking Groq model {model} for a minimal patch...")
        patch = await _propose_patch(issue, context, model)
        patch_files = ensure_source_patch_only(patch.files)
        print(f"Patch summary: {patch.summary or '(no summary)'}")
        for patch_file in patch_files:
            print(f"  - {patch_file.path}")

        print("\nCreating E2B sandbox...")
        sandbox = await create_e2b_sandbox(timeout=args.sandbox_timeout)
        print(f"Sandbox ready (id: {sandbox_identifier(sandbox)})")

        file_count = await write_project_to_sandbox(
            sandbox, project_root, args.sandbox_root
        )
        print(f"Wrote {file_count} files to {args.sandbox_root}")

        await run_sandbox_command(
            sandbox,
            "git init -q && git add .",
            cwd=args.sandbox_root,
            timeout=30,
        )

        if args.setup_command:
            setup = await run_sandbox_command(
                sandbox,
                args.setup_command,
                cwd=args.sandbox_root,
                timeout=args.setup_timeout,
            )
            _print_command("Setup command", setup)
            if not setup.ok:
                return False

        baseline = await run_tests(
            sandbox,
            command=args.test_command,
            cwd=args.sandbox_root,
            timeout=args.test_timeout,
        )
        _print_command("Baseline tests", baseline)

        await apply_patch_files(sandbox, patch_files, args.sandbox_root)
        validation = await run_tests(
            sandbox,
            command=args.test_command,
            cwd=args.sandbox_root,
            timeout=args.test_timeout,
        )
        _print_command("Patched tests", validation)

        pathspec = _git_pathspec(patch_files)
        diff = await run_sandbox_command(
            sandbox,
            f"git add -N -- {pathspec} && git diff -- {pathspec}",
            cwd=args.sandbox_root,
            timeout=30,
        )
        if diff.stdout.strip():
            print("\nValidated patch diff:")
            print(textwrap.indent(diff.stdout.strip(), "  "))

        return validation.ok

    finally:
        if sandbox is not None and not args.keep_sandbox:
            print("\nCleaning up E2B sandbox...")
            try:
                await sandbox.kill()
            except Exception as exc:
                print(f"Warning: sandbox cleanup failed: {exc}")

        if moss_client is not None and created_index and not args.reuse_index:
            print(f"Deleting Moss index '{index_name}'...")
            try:
                await moss_client.delete_index(index_name)
            except Exception as exc:
                print(f"Warning: index cleanup failed: {exc}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Self-healing code agent - Moss + E2B")
    parser.add_argument(
        "--project-root",
        default=str(SAMPLE_PROJECT),
        help="Local project to copy into E2B",
    )
    parser.add_argument(
        "--issue", default=DEFAULT_ISSUE, help="Bug report or task to repair"
    )
    parser.add_argument(
        "--index-name",
        default=None,
        help=(
            "Moss index name; defaults to a unique temporary index, or "
            f"{DEFAULT_REUSABLE_INDEX_NAME!r} with --reuse-index"
        ),
    )
    parser.add_argument(
        "--reuse-index",
        action="store_true",
        help=(
            "Load an existing Moss index instead of recreating it. If the index "
            "does not exist, create it and keep it for future runs."
        ),
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=6,
        help="Moss results to include in the patch prompt",
    )
    parser.add_argument(
        "--alpha", type=float, default=0.75, help="Moss hybrid search blend"
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Groq model; defaults to GROQ_MODEL or llama-3.3-70b-versatile",
    )
    parser.add_argument(
        "--sandbox-root", default=DEFAULT_SANDBOX_ROOT, help="Workspace path inside E2B"
    )
    parser.add_argument(
        "--sandbox-timeout",
        type=int,
        default=600,
        help="E2B sandbox lifetime in seconds",
    )
    parser.add_argument(
        "--setup-command",
        default="python -m pip install -q pytest",
        help="Command run before tests",
    )
    parser.add_argument(
        "--setup-timeout",
        type=float,
        default=180,
        help="Setup command timeout in seconds",
    )
    parser.add_argument(
        "--test-command", default="python -m pytest -q", help="Validation command"
    )
    parser.add_argument(
        "--test-timeout",
        type=float,
        default=120,
        help="Test command timeout in seconds",
    )
    parser.add_argument(
        "--keep-sandbox",
        action="store_true",
        help="Do not kill the E2B sandbox after running",
    )
    return parser


async def main() -> int:
    args = build_parser().parse_args()
    ok = await run_code_repair(args)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

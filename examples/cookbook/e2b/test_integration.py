"""Mocked tests for the Moss + E2B cookbook helpers."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from code_agent import DEFAULT_REUSABLE_INDEX_NAME, _resolve_index_name
from code_index import extract_python_symbols, iter_source_files
from sandbox_runner import (
    DEFAULT_SANDBOX_ROOT,
    PatchFile,
    apply_patch_files,
    ensure_source_patch_only,
    iter_project_files,
    parse_patch_json,
    run_sandbox_command,
    write_project_to_sandbox,
)


class FakeFiles:
    def __init__(self):
        self.writes = {}

    async def write(self, path, data):
        self.writes[path] = data


class FakeCommands:
    def __init__(self, stdout="", stderr="", exit_code=0):
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.calls = []

    async def run(self, command, cwd=None, timeout=None):
        self.calls.append((command, cwd, timeout))
        return SimpleNamespace(
            stdout=self.stdout,
            stderr=self.stderr,
            exit_code=self.exit_code,
        )


class FakeSandbox:
    def __init__(self, stdout="", stderr="", exit_code=0):
        self.files = FakeFiles()
        self.commands = FakeCommands(stdout, stderr, exit_code)


class CodeIndexTests(unittest.TestCase):
    def test_extract_python_symbols(self):
        source = """
class Cart:
    pass

def format_total():
    pass

async def load_cart():
    pass
"""

        self.assertEqual(
            extract_python_symbols(source), ["Cart", "format_total", "load_cart"]
        )

    def test_iter_source_files_skips_ignored_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("print('ok')", encoding="utf-8")
            (root / "Makefile").write_text("test:\n\tpytest\n", encoding="utf-8")
            (root / ".venv").mkdir()
            (root / ".venv" / "ignored.py").write_text("print('no')", encoding="utf-8")
            (root / "blob.png").write_bytes(b"no")

            files = [
                path.relative_to(root).as_posix() for path in iter_source_files(root)
            ]

        self.assertEqual(files, ["src/app.py"])

    def test_iter_project_files_includes_runnable_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("print('ok')", encoding="utf-8")
            (root / "Makefile").write_text("test:\n\tpytest\n", encoding="utf-8")
            (root / ".env").write_text("secret", encoding="utf-8")
            (root / ".env.local").write_text("secret", encoding="utf-8")

            files = [
                path.relative_to(root).as_posix() for path in iter_project_files(root)
            ]

        self.assertEqual(files, ["Makefile", "src/app.py"])


class CodeAgentConfigTests(unittest.TestCase):
    def test_resolve_index_name_prefers_explicit_name(self):
        args = SimpleNamespace(index_name="my-index", reuse_index=True)

        self.assertEqual(_resolve_index_name(args), "my-index")

    def test_resolve_index_name_uses_reusable_default_with_reuse_flag(self):
        args = SimpleNamespace(index_name=None, reuse_index=True)

        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(_resolve_index_name(args), DEFAULT_REUSABLE_INDEX_NAME)

    def test_resolve_index_name_uses_env_name(self):
        args = SimpleNamespace(index_name=None, reuse_index=False)

        with patch.dict(os.environ, {"MOSS_INDEX_NAME": "env-index"}, clear=True):
            self.assertEqual(_resolve_index_name(args), "env-index")


class SandboxRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_write_project_to_sandbox_uses_posix_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("print('ok')", encoding="utf-8")
            (root / "pyproject.toml").write_bytes(b"[project]\nname = 'x'\n")
            sandbox = FakeSandbox()

            count = await write_project_to_sandbox(sandbox, root, DEFAULT_SANDBOX_ROOT)

        self.assertEqual(count, 2)
        self.assertEqual(
            sandbox.files.writes[f"{DEFAULT_SANDBOX_ROOT}/src/app.py"],
            b"print('ok')",
        )
        self.assertEqual(
            sandbox.files.writes[f"{DEFAULT_SANDBOX_ROOT}/pyproject.toml"],
            b"[project]\nname = 'x'\n",
        )

    async def test_apply_patch_files_rejects_path_traversal(self):
        sandbox = FakeSandbox()

        with self.assertRaises(ValueError):
            await apply_patch_files(
                sandbox,
                [PatchFile("../outside.py", "print('no')")],
                DEFAULT_SANDBOX_ROOT,
            )

    async def test_run_sandbox_command_parses_wrapped_exit_code(self):
        stdout = "tests failed\n__MOSS_COMMAND_EXIT_CODE__=2\n"
        sandbox = FakeSandbox(stdout=stdout, stderr="details", exit_code=0)

        result = await run_sandbox_command(sandbox, "python -m pytest -q")

        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.stdout, "tests failed")
        self.assertEqual(result.stderr, "details")
        self.assertFalse(result.ok)
        self.assertIn("bash -lc", sandbox.commands.calls[0][0])


class PatchParsingTests(unittest.TestCase):
    def test_parse_patch_json_accepts_fenced_json(self):
        raw = """```json
{"summary": "fix tax", "files": [{"path": "src/ledger/totals.py", "content": "fixed"}]}
```"""

        patch = parse_patch_json(raw)

        self.assertEqual(patch.summary, "fix tax")
        self.assertEqual(patch.files, [PatchFile("src/ledger/totals.py", "fixed")])

    def test_parse_patch_json_accepts_content_lines(self):
        raw = """
{
  "summary": "fix tax",
  "files": [
    {
      "path": "src/ledger/totals.py",
      "content_lines": [
        "from decimal import Decimal",
        "",
        "def total(subtotal: Decimal, tax_rate: Decimal) -> Decimal:",
        "    return subtotal + (subtotal * tax_rate)"
      ]
    }
  ]
}
"""

        patch = parse_patch_json(raw)

        self.assertEqual(patch.summary, "fix tax")
        self.assertEqual(
            patch.files,
            [
                PatchFile(
                    "src/ledger/totals.py",
                    "from decimal import Decimal\n\n"
                    "def total(subtotal: Decimal, tax_rate: Decimal) -> Decimal:\n"
                    "    return subtotal + (subtotal * tax_rate)\n",
                )
            ],
        )

    def test_parse_patch_json_rejects_absolute_paths(self):
        raw = '{"summary": "bad", "files": [{"path": "/tmp/x.py", "content": "bad"}]}'

        with self.assertRaises(ValueError):
            parse_patch_json(raw)

    def test_ensure_source_patch_only_rejects_tests(self):
        with self.assertRaises(ValueError):
            ensure_source_patch_only([PatchFile("tests/test_totals.py", "pass")])


if __name__ == "__main__":
    unittest.main()

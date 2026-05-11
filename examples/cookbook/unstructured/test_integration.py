import asyncio
import contextlib
import importlib
import io
import sys
import types
import unittest
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch


@dataclass
class FakeDocumentInfo:
    id: str
    text: str
    metadata: dict[str, str] | None = None


class FakeMutationOptions:
    def __init__(self, upsert: bool = False):
        self.upsert = upsert


class FakeQueryOptions:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


STUBBED_MODULES = [
    "dotenv",
    "moss",
    "unstructured",
    "unstructured.chunking",
    "unstructured.chunking.title",
    "unstructured.partition",
    "unstructured.partition.auto",
]


def _install_dependency_stubs() -> dict[str, types.ModuleType | None]:
    previous_modules = {name: sys.modules.get(name) for name in STUBBED_MODULES}

    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda: None

    moss = types.ModuleType("moss")
    moss.DocumentInfo = FakeDocumentInfo
    moss.MossClient = object
    moss.MutationOptions = FakeMutationOptions
    moss.QueryOptions = FakeQueryOptions

    unstructured = types.ModuleType("unstructured")
    chunking = types.ModuleType("unstructured.chunking")
    title = types.ModuleType("unstructured.chunking.title")
    title.chunk_by_title = lambda *args, **kwargs: []
    partition = types.ModuleType("unstructured.partition")
    auto = types.ModuleType("unstructured.partition.auto")
    auto.partition = lambda *args, **kwargs: []

    sys.modules["dotenv"] = dotenv
    sys.modules["moss"] = moss
    sys.modules["unstructured"] = unstructured
    sys.modules["unstructured.chunking"] = chunking
    sys.modules["unstructured.chunking.title"] = title
    sys.modules["unstructured.partition"] = partition
    sys.modules["unstructured.partition.auto"] = auto
    return previous_modules


def _restore_modules(previous_modules: dict[str, types.ModuleType | None]) -> None:
    for name, module in previous_modules.items():
        if module is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = module


_PREVIOUS_MODULES = _install_dependency_stubs()

ingest = importlib.import_module("ingest")

_restore_modules(_PREVIOUS_MODULES)


class FakeMetadata:
    def to_dict(self):
        return {
            "page_number": 4,
            "languages": ["eng"],
            "orig_elements": ["too large for Moss metadata"],
            "empty": None,
        }


class FakeElement:
    category = "CompositeElement"

    def __init__(self, text: str, element_id: str | None = None):
        self.text = text
        self.id = element_id
        self.metadata = FakeMetadata()

    def __str__(self):
        return self.text


class TestUnstructuredIngestion(unittest.TestCase):
    def test_file_to_documents_preserves_metadata_and_stable_ids(self):
        with TemporaryDirectory() as temp_dir:
            input_dir = Path(temp_dir)
            source = input_dir / "policies" / "onboarding.html"
            source.parent.mkdir()
            source.write_text("<h1>Onboarding</h1>", encoding="utf-8")

            chunks = [
                FakeElement(
                    "Employees receive laptop access during onboarding.",
                    "el-1",
                ),
                FakeElement("   "),
                FakeElement("Security reviews happen quarterly.", "el-2"),
            ]

            with (
                patch.object(
                    ingest,
                    "partition",
                    return_value=["raw-element"],
                ) as partition,
                patch.object(
                    ingest,
                    "chunk_by_title",
                    return_value=chunks,
                ) as chunk_by_title,
            ):
                docs = ingest.file_to_documents(source, input_dir)

            partition.assert_called_once_with(filename=str(source))
            chunk_by_title.assert_called_once()
            self.assertEqual(len(docs), 2)
            self.assertEqual(docs[0].id, "policies/onboarding.html::chunk-0000")
            self.assertEqual(docs[1].id, "policies/onboarding.html::chunk-0002")
            self.assertEqual(
                docs[0].text,
                "Employees receive laptop access during onboarding.",
            )
            self.assertEqual(
                docs[0].metadata["source_path"],
                "policies/onboarding.html",
            )
            self.assertEqual(docs[0].metadata["filename"], "onboarding.html")
            self.assertEqual(docs[0].metadata["filetype"], ".html")
            self.assertEqual(docs[0].metadata["chunk_index"], "0")
            self.assertEqual(docs[0].metadata["category"], "CompositeElement")
            self.assertEqual(docs[0].metadata["page_number"], "4")
            self.assertEqual(docs[0].metadata["languages"], '["eng"]')
            self.assertEqual(docs[0].metadata["element_id"], "el-1")
            self.assertNotIn("orig_elements", docs[0].metadata)
            self.assertNotIn("empty", docs[0].metadata)
            self.assertEqual(len(docs[0].metadata["text_hash"]), 12)

    def test_upsert_documents_creates_index_then_upserts_remaining_batches(self):
        client = types.SimpleNamespace(
            create_index=AsyncMock(),
            add_docs=AsyncMock(),
        )
        docs = [
            FakeDocumentInfo(id="doc-1", text="one"),
            FakeDocumentInfo(id="doc-2", text="two"),
            FakeDocumentInfo(id="doc-3", text="three"),
        ]

        with contextlib.redirect_stdout(io.StringIO()):
            asyncio.run(ingest.upsert_documents(client, "unstructured-test", docs, 2))

        client.create_index.assert_awaited_once_with("unstructured-test", docs[:2])
        client.add_docs.assert_awaited_once()
        args = client.add_docs.await_args.args
        self.assertEqual(args[0], "unstructured-test")
        self.assertEqual(args[1], docs[2:])
        self.assertTrue(args[2].upsert)

    def test_upsert_documents_upserts_all_batches_when_index_exists(self):
        client = types.SimpleNamespace(
            create_index=AsyncMock(side_effect=RuntimeError("index already exists")),
            add_docs=AsyncMock(),
        )
        docs = [
            FakeDocumentInfo(id="doc-1", text="one"),
            FakeDocumentInfo(id="doc-2", text="two"),
            FakeDocumentInfo(id="doc-3", text="three"),
        ]

        with contextlib.redirect_stdout(io.StringIO()):
            asyncio.run(ingest.upsert_documents(client, "unstructured-test", docs, 2))

        self.assertEqual(client.add_docs.await_count, 2)
        first_call, second_call = client.add_docs.await_args_list
        self.assertEqual(first_call.args[1], docs[:2])
        self.assertEqual(second_call.args[1], docs[2:])


if __name__ == "__main__":
    unittest.main()

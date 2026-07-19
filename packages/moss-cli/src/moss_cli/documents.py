"""Load documents from JSON/CSV files or stdin."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any, List

import typer
from moss import DocumentInfo


def load_documents(file_path: str) -> List[DocumentInfo]:
    """Load documents from a JSON/CSV file or stdin ('-')."""
    if file_path == "-":
        raw = sys.stdin.read()
        return _parse_json_docs(raw, source="stdin")

    path = Path(file_path)
    if not path.exists():
        raise typer.BadParameter(f"File not found: {file_path}")

    suffix = path.suffix.lower()
    content = path.read_text()

    if suffix == ".csv":
        return _parse_csv_docs(content)
    elif suffix == ".jsonl":
        return _parse_jsonl_docs(content, source=file_path)
    elif suffix == ".json":
        return _parse_json_docs(content, source=file_path)
    else:
        return _parse_json_docs(content, source=file_path)


def _parse_json_docs(raw: str, source: str = "input") -> List[DocumentInfo]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise typer.BadParameter(f"Invalid JSON in {source}: {e}")

    if isinstance(data, dict):
        data = data.get("documents", data.get("docs", []))

    if not isinstance(data, list):
        raise typer.BadParameter(
            f"Expected a JSON array of documents, got {type(data).__name__}"
        )

    return [_dict_to_doc(d, i) for i, d in enumerate(data)]


def _parse_jsonl_docs(raw: str, source: str = "input") -> List[DocumentInfo]:
    docs = []
    for line_no, line in enumerate(raw.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            raise typer.BadParameter(f"Invalid JSON on line {line_no} in {source}: {e}")
        docs.append(_dict_to_doc(obj, line_no - 1))
    return docs


def _parse_csv_docs(content: str) -> List[DocumentInfo]:
    reader = csv.DictReader(content.splitlines())
    docs = []
    for i, row in enumerate(reader):
        if "id" not in row or "text" not in row:
            raise typer.BadParameter(
                f"CSV row {i + 1}: missing required 'id' or 'text' column"
            )
        metadata = None
        if "metadata" in row and row["metadata"]:
            try:
                metadata = json.loads(row["metadata"])
            except json.JSONDecodeError:
                raise typer.BadParameter(
                    f"CSV row {i + 1}: invalid JSON in 'metadata' column"
                )

        embedding = None
        if "embedding" in row and row["embedding"]:
            try:
                embedding = json.loads(row["embedding"])
            except json.JSONDecodeError:
                raise typer.BadParameter(
                    f"CSV row {i + 1}: invalid JSON in 'embedding' column"
                )

        docs.append(
            DocumentInfo(
                id=row["id"],
                text=row["text"],
                metadata=metadata,
                embedding=embedding,
            )
        )
    return docs


def _dict_to_doc(d: Any, index: int) -> DocumentInfo:
    if not isinstance(d, dict):
        raise typer.BadParameter(f"Document at index {index}: expected object, got {type(d).__name__}")
    if "id" not in d or "text" not in d:
        raise typer.BadParameter(f"Document at index {index}: missing required 'id' or 'text' field")
    return DocumentInfo(
        id=str(d["id"]),
        text=str(d["text"]),
        metadata=d.get("metadata"),
        embedding=d.get("embedding"),
    )


def import_csv_docs(
    content: str,
    id_column: str = "id",
    text_column: str = "text",
    metadata_columns: Optional[List[str]] = None,
    include_all_metadata: bool = True,
) -> List[DocumentInfo]:
    reader = csv.DictReader(content.splitlines())
    docs = []
    for i, row in enumerate(reader):
        if id_column not in row:
            raise typer.BadParameter(
                f"CSV row {i + 1}: missing mapped ID column '{id_column}'"
            )
        if text_column not in row:
            raise typer.BadParameter(
                f"CSV row {i + 1}: missing mapped text column '{text_column}'"
            )

        doc_id = row[id_column]
        doc_text = row[text_column]

        metadata = {}
        if metadata_columns is not None:
            for col in metadata_columns:
                if col in row:
                    val = row[col]
                    if isinstance(val, (dict, list)):
                        metadata[col] = json.dumps(val)
                    elif val is not None:
                        metadata[col] = str(val)
        elif include_all_metadata:
            for col, val in row.items():
                if col not in (id_column, text_column, "embedding") and val is not None:
                    metadata[col] = str(val)

        embedding = None
        if "embedding" in row and row["embedding"] and "embedding" not in (id_column, text_column):
            try:
                embedding = json.loads(row["embedding"])
            except json.JSONDecodeError:
                raise typer.BadParameter(
                    f"CSV row {i + 1}: invalid JSON in 'embedding' column"
                )

        docs.append(
            DocumentInfo(
                id=str(doc_id),
                text=str(doc_text),
                metadata=metadata if metadata else None,
                embedding=embedding,
            )
        )
    return docs


def import_json_docs(
    raw: str,
    source: str = "input",
    id_column: str = "id",
    text_column: str = "text",
    metadata_columns: Optional[List[str]] = None,
    include_all_metadata: bool = True,
) -> List[DocumentInfo]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise typer.BadParameter(f"Invalid JSON in {source}: {e}")

    if isinstance(data, dict):
        data = data.get("documents", data.get("docs", []))

    if not isinstance(data, list):
        raise typer.BadParameter(
            f"Expected a JSON array of documents, got {type(data).__name__}"
        )

    return [
        _dict_to_mapped_doc(
            d,
            i,
            id_column=id_column,
            text_column=text_column,
            metadata_columns=metadata_columns,
            include_all_metadata=include_all_metadata,
        )
        for i, d in enumerate(data)
    ]


def import_jsonl_docs(
    raw: str,
    source: str = "input",
    id_column: str = "id",
    text_column: str = "text",
    metadata_columns: Optional[List[str]] = None,
    include_all_metadata: bool = True,
) -> List[DocumentInfo]:
    docs = []
    for line_no, line in enumerate(raw.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            raise typer.BadParameter(f"Invalid JSON on line {line_no} in {source}: {e}")
        docs.append(
            _dict_to_mapped_doc(
                obj,
                line_no - 1,
                id_column=id_column,
                text_column=text_column,
                metadata_columns=metadata_columns,
                include_all_metadata=include_all_metadata,
            )
        )
    return docs


def _dict_to_mapped_doc(
    d: Any,
    index: int,
    id_column: str = "id",
    text_column: str = "text",
    metadata_columns: Optional[List[str]] = None,
    include_all_metadata: bool = True,
) -> DocumentInfo:
    if not isinstance(d, dict):
        raise typer.BadParameter(f"Document at index {index}: expected object, got {type(d).__name__}")
    if id_column not in d:
        raise typer.BadParameter(f"Document at index {index}: missing mapped ID field '{id_column}'")
    if text_column not in d:
        raise typer.BadParameter(f"Document at index {index}: missing mapped text field '{text_column}'")

    doc_id = d[id_column]
    doc_text = d[text_column]

    metadata = {}
    if metadata_columns is not None:
        for col in metadata_columns:
            if col in d:
                val = d[col]
                if isinstance(val, (dict, list)):
                    metadata[col] = json.dumps(val)
                elif val is not None:
                    metadata[col] = str(val)
    elif include_all_metadata:
        for col, val in d.items():
            if col not in (id_column, text_column, "embedding") and val is not None:
                if isinstance(val, (dict, list)):
                    metadata[col] = json.dumps(val)
                else:
                    metadata[col] = str(val)

    embedding = d.get("embedding")

    return DocumentInfo(
        id=str(doc_id),
        text=str(doc_text),
        metadata=metadata if metadata else None,
        embedding=embedding,
    )


def import_documents(
    file_path: str,
    id_column: str = "id",
    text_column: str = "text",
    metadata_columns: Optional[List[str]] = None,
    include_all_metadata: bool = True,
) -> List[DocumentInfo]:
    """Import documents from a JSON/CSV file or stdin ('-') with column mapping."""
    if file_path == "-":
        raw = sys.stdin.read()
        return import_json_docs(
            raw,
            source="stdin",
            id_column=id_column,
            text_column=text_column,
            metadata_columns=metadata_columns,
            include_all_metadata=include_all_metadata,
        )

    path = Path(file_path)
    if not path.exists():
        raise typer.BadParameter(f"File not found: {file_path}")

    suffix = path.suffix.lower()
    content = path.read_text()

    if suffix == ".csv":
        return import_csv_docs(
            content,
            id_column=id_column,
            text_column=text_column,
            metadata_columns=metadata_columns,
            include_all_metadata=include_all_metadata,
        )
    elif suffix == ".jsonl":
        return import_jsonl_docs(
            content,
            source=file_path,
            id_column=id_column,
            text_column=text_column,
            metadata_columns=metadata_columns,
            include_all_metadata=include_all_metadata,
        )
    elif suffix == ".json":
        return import_json_docs(
            content,
            source=file_path,
            id_column=id_column,
            text_column=text_column,
            metadata_columns=metadata_columns,
            include_all_metadata=include_all_metadata,
        )
    else:
        return import_json_docs(
            content,
            source=file_path,
            id_column=id_column,
            text_column=text_column,
            metadata_columns=metadata_columns,
            include_all_metadata=include_all_metadata,
        )

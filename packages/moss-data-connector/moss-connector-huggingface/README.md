# moss-connector-huggingface

HuggingFace Datasets source connector for Moss. Streams any public or private
dataset from the [HuggingFace Hub](https://huggingface.co/datasets) directly
into a Moss index via the [`datasets`](https://huggingface.co/docs/datasets)
library.

## Install

```bash
pip install moss-connector-huggingface
```

This pulls `datasets` as a dependency. For gated or private datasets you also
need a HuggingFace account and a `HF_TOKEN`.

## Usage — Hub dataset (streaming)

```python
import asyncio
from moss import DocumentInfo
from moss_connector_huggingface import HuggingFaceDatasetConnector, ingest

async def main():
    source = HuggingFaceDatasetConnector(
        dataset_name="ag_news",
        split="train",
        mapper=lambda row: DocumentInfo(
            id=str(row["label"]) + "-" + row["text"][:8],
            text=row["text"],
            metadata={"category": str(row["label"])},
        ),
    )

    result = await ingest(
        source,
        project_id="your_project_id",
        project_key="your_project_key",
        index_name="ag-news",
    )
    print(f"ingested {result.doc_count} rows")

asyncio.run(main())
```

Use `auto_id=True` when you don't have a stable primary key and want Moss to
generate UUID document IDs.

## Usage — Local files

```python
from moss_connector_huggingface import HuggingFaceLocalDatasetConnector, ingest

source = HuggingFaceLocalDatasetConnector(
    data_files="articles.jsonl",
    format="json",          # inferred from extension if omitted
    mapper=lambda row: DocumentInfo(
        id=row["id"],
        text=row["body"],
        metadata={"title": row["title"]},
    ),
)
```

Accepts any format supported by `datasets`: `json` / `jsonl`, `csv`, `parquet`,
`arrow`, `text`.

## Filtering rows

Pass a ``filter_fn`` to restrict which rows are ingested:

```python
HuggingFaceDatasetConnector(
    dataset_name="ag_news",
    split="train",
    filter_fn=lambda row: row["label"] == 3,   # Sci/Tech only
    mapper=...,
)
```

The filter runs in Python after the dataset is loaded — it does not reduce
download or streaming volume, but it is zero-config and works on any field.

## Subsets and slices

```python
# Wikipedia English subset
HuggingFaceDatasetConnector(
    dataset_name="wikipedia",
    name="20220301.en",          # subset/config name
    split="train[:500]",         # first 500 rows
    mapper=...,
)

# Gated dataset
HuggingFaceDatasetConnector(
    dataset_name="meta-llama/Llama-3.2-1B",
    token="hf_...",              # or set HF_TOKEN env var
    split="train",
    mapper=...,
)
```

## Data requirements

`DocumentInfo.metadata` requires `Dict[str, str]`. HuggingFace row values can
be ints, floats, lists, etc. — coerce them in your mapper:

```python
mapper=lambda row: DocumentInfo(
    id=str(row["id"]),
    text=row["text"],
    metadata={
        "label":  str(row["label"]),          # int → str
        "score":  f"{row['score']:.4f}",      # float → str
        "tags":   ",".join(row["tags"]),      # list → str
    },
)
```

## Layout

```
src/
├── __init__.py      # re-exports HuggingFaceDatasetConnector,
│                    #           HuggingFaceLocalDatasetConnector, ingest
├── connector.py     # connector classes
└── ingest.py        # ingest() — kept in sync with other connector packages
```

## Tests

```bash
pip install -e ".[dev]"
pytest tests/test_huggingface.py -v                           # mocked, no network
pytest tests/test_integration_huggingface_moss.py -v -s       # live HF + Moss
```

The unit tests mock `datasets.load_dataset` — no HuggingFace token or network
connection needed.

The integration test uses the public `ag_news` dataset (20-row slice) and
requires `MOSS_PROJECT_ID` and `MOSS_PROJECT_KEY`.  Set `HF_TOKEN` only for
gated datasets.

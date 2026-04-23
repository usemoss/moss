# moss-connector-template

Starting point for a new connector. Not a real package, don't install it.

## To create a new connector

```bash
cd packages/moss-data-connector
cp -r _template moss-connector-<source>
cd moss-connector-<source>
```

Then:

1. Open `pyproject.toml` and replace every `TODO` (name, description, keywords, Source URL, driver deps). The package name is `moss-connector-<source>`, the Python module is `moss_connector_<source>`.
2. Open `src/connector.py` and:
   - Rename `TemplateConnector` → `<Source>Connector`.
   - Add your source-specific config to `__init__`.
   - Implement `__iter__` (connect, pull rows, `yield self.mapper(row)`).
3. Update `src/__init__.py` to re-export your renamed class.
4. Rename `tests/test_template.py` → `tests/test_<source>.py` and fill in.
5. Add a live integration test in `tests/test_integration_<source>_moss.py` if you can (see sqlite/mongodb for patterns).
6. Update this package's README with install + usage snippets (see `moss-connector-sqlite/README.md` for shape).
7. Add a row to `packages/moss-data-connector/README.md`.
8. Open a PR.

## Rules

- **One source per package.** Don't combine.
- **Declare your driver as a main dependency** in `pyproject.toml` and import it at the top of the module.
- **No retries or rate-limit logic in `ingest.py`.** If a connector needs it, put it in the connector's own code.

## Caller shape (what users write against your connector)

```python
from moss import DocumentInfo
from moss_connector_<source> import <Source>Connector, ingest

source = <Source>Connector(
    # your config here
    mapper=lambda r: DocumentInfo(
        id=str(r["id"]),
        text=r["body"],
        metadata={"title": r["title"]},
    ),
)

await ingest(source, project_id="...", project_key="...", index_name="articles")
```

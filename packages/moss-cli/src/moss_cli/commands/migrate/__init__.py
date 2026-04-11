"""moss migrate -- data migration from external vector DBs and files."""

from __future__ import annotations

import asyncio
from typing import Optional

import typer

from ...context import get_client, get_ctx
from ...errors import CliValidationError
from .adapters.base import SourceAdapter
from .checkpoint import CheckpointStore
from .engine import MigrationEngine
from .sink import MossSink

migrate_app = typer.Typer(name="migrate", help="Migrate data from other vector DBs")


@migrate_app.callback(invoke_without_command=True)
def migrate_command(
    ctx: typer.Context,
    source_type: str = typer.Option(
        ..., "--from", help="Source type (json, pinecone)"
    ),
    target_index: str = typer.Option(
        ..., "--target-index", "-t", help="Moss target index name"
    ),
    # JSON source options
    source_file: Optional[str] = typer.Option(
        None, "--source-file", help="Path to JSON/JSONL file (for --from json)"
    ),
    # Pinecone source options
    source_index: Optional[str] = typer.Option(
        None, "--source-index", help="Pinecone index name (for --from pinecone)"
    ),
    source_environment: Optional[str] = typer.Option(
        None, "--source-environment", help="Pinecone environment (for --from pinecone)"
    ),
    source_api_key_file: Optional[str] = typer.Option(
        None, "--source-api-key-file", help="Path to file containing source API key"
    ),
    # General options
    batch_size: int = typer.Option(
        1000, "--batch-size", "-b", help="Documents per batch"
    ),
    re_embed: bool = typer.Option(
        False, "--re-embed", help="Re-embed with Moss model instead of keeping original vectors"
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m", help="Moss model for re-embed (default: moss-minilm)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview migration without writing data"
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip confirmation prompt"
    ),
    resume: bool = typer.Option(
        False, "--resume", help="Resume from last checkpoint"
    ),
) -> None:
    """Migrate data into a Moss index from an external source."""
    if ctx.invoked_subcommand is not None:
        return

    cli = get_ctx(ctx)
    adapter = _build_adapter(source_type, source_file, source_index, source_environment, source_api_key_file)

    # Preview
    adapter.connect()
    preview = adapter.preview()

    if not dry_run and not yes and not cli.no_input and not cli.json_output:
        typer.confirm(
            f"Migrate {preview.doc_count} documents to '{target_index}'?",
            abort=True,
        )

    client = get_client(ctx)
    sink = MossSink(client=client, index_name=target_index, re_embed=re_embed, model=model)
    checkpoint = CheckpointStore(target_index)
    engine = MigrationEngine(source=adapter, sink=sink, checkpoint=checkpoint)

    asyncio.run(
        engine.run(
            batch_size=batch_size,
            resume=resume,
            dry_run=dry_run,
            json_mode=cli.json_output,
        )
    )


def _build_adapter(
    source_type: str,
    source_file: Optional[str],
    source_index: Optional[str],
    source_environment: Optional[str],
    source_api_key_file: Optional[str],
) -> SourceAdapter:
    """Construct the appropriate SourceAdapter based on --from flag."""
    if source_type == "json":
        if not source_file:
            raise CliValidationError(
                "--source-file is required when --from is 'json'",
                hint="Use --source-file path/to/data.json",
            )
        from .adapters.json_file import JsonFileAdapter

        return JsonFileAdapter(source_file)

    elif source_type == "pinecone":
        if not source_index:
            raise CliValidationError(
                "--source-index is required when --from is 'pinecone'",
                hint="Use --source-index your-pinecone-index",
            )
        if not source_environment:
            raise CliValidationError(
                "--source-environment is required when --from is 'pinecone'",
                hint="Use --source-environment us-east-1",
            )
        from .adapters.pinecone import PineconeAdapter

        return PineconeAdapter(
            index_name=source_index,
            environment=source_environment,
            api_key_file=source_api_key_file,
        )

    else:
        supported = ["json", "pinecone"]
        raise CliValidationError(
            f"Unknown source type: '{source_type}'",
            hint=f"Supported sources: {', '.join(supported)}",
        )

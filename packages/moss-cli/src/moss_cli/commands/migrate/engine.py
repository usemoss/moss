"""MigrationEngine -- orchestrates source -> sink migration."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from ...output import _print_json
from .adapters.base import SourceAdapter, SourcePreview
from .checkpoint import CheckpointStore
from .sink import MossSink

console = Console()


@dataclass
class MigrationResult:
    """Final report from a migration run."""

    source_doc_count: int
    migrated: int
    failed: int
    batches: int
    elapsed_seconds: float
    job_ids: List[str] = field(default_factory=list)
    resumed_from: Optional[int] = None

    def to_dict(self) -> dict:
        d = {
            "source_doc_count": self.source_doc_count,
            "migrated": self.migrated,
            "failed": self.failed,
            "batches": self.batches,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "job_ids": self.job_ids,
        }
        if self.resumed_from is not None:
            d["resumed_from_batch"] = self.resumed_from
        return d


class MigrationEngine:
    """Orchestrates: connect -> preview -> stream -> write -> checkpoint -> report."""

    def __init__(
        self,
        source: SourceAdapter,
        sink: MossSink,
        checkpoint: CheckpointStore,
    ) -> None:
        self._source = source
        self._sink = sink
        self._checkpoint = checkpoint

    def preview(self) -> SourcePreview:
        """Connect to source and return a preview."""
        self._source.connect()
        return self._source.preview()

    async def run(
        self,
        batch_size: int,
        resume: bool,
        dry_run: bool,
        json_mode: bool,
    ) -> MigrationResult:
        """Execute the migration."""
        start = time.monotonic()

        # Connect and preview
        self._source.connect()
        src_preview = self._source.preview()

        # Handle dry run
        if dry_run:
            elapsed = time.monotonic() - start
            result = MigrationResult(
                source_doc_count=src_preview.doc_count,
                migrated=0,
                failed=0,
                batches=0,
                elapsed_seconds=elapsed,
            )
            if json_mode:
                _print_json({"dry_run": True, "preview": self._preview_dict(src_preview), **result.to_dict()})
            else:
                self._print_preview(src_preview)
                console.print("[yellow]Dry run -- no data was written.[/yellow]")
            return result

        # Resume logic
        start_batch = 0
        total_migrated = 0
        resumed_from: Optional[int] = None
        if resume:
            ckpt = self._checkpoint.load()
            if ckpt is not None:
                start_batch, total_migrated = ckpt
                resumed_from = start_batch
                if not json_mode:
                    console.print(
                        f"[yellow]Resuming from batch {start_batch} "
                        f"({total_migrated} docs already migrated)[/yellow]"
                    )

        # Ensure target index exists
        await self._sink.ensure_index(src_preview)

        # Stream and write
        batch_num = 0
        failed = 0
        job_ids: List[str] = []

        if json_mode:
            # No progress bar in JSON mode
            for batch in self._source.stream(batch_size=batch_size):
                if batch_num < start_batch:
                    batch_num += 1
                    continue
                try:
                    job_id = await self._sink.write_batch(batch)
                    job_ids.append(job_id)
                    total_migrated += len(batch)
                except Exception:
                    failed += len(batch)
                batch_num += 1
                self._checkpoint.save(batch_num, total_migrated)
        else:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("{task.completed}/{task.total} docs"),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(
                    "Migrating...",
                    total=src_preview.doc_count,
                    completed=total_migrated,
                )
                for batch in self._source.stream(batch_size=batch_size):
                    if batch_num < start_batch:
                        batch_num += 1
                        progress.update(task, advance=len(batch))
                        continue
                    try:
                        job_id = await self._sink.write_batch(batch)
                        job_ids.append(job_id)
                        total_migrated += len(batch)
                    except Exception:
                        failed += len(batch)
                    progress.update(task, advance=len(batch))
                    batch_num += 1
                    self._checkpoint.save(batch_num, total_migrated)

        # Clean up checkpoint on success
        if failed == 0:
            self._checkpoint.clear()

        self._source.close()

        elapsed = time.monotonic() - start
        result = MigrationResult(
            source_doc_count=src_preview.doc_count,
            migrated=total_migrated,
            failed=failed,
            batches=batch_num,
            elapsed_seconds=elapsed,
            job_ids=job_ids,
            resumed_from=resumed_from,
        )

        if json_mode:
            _print_json(result.to_dict())
        else:
            self._print_result(result)

        return result

    @staticmethod
    def _preview_dict(preview: SourcePreview) -> dict:
        return {
            "doc_count": preview.doc_count,
            "dimensions": preview.dimensions,
            "metadata_fields": preview.metadata_fields,
            "extra": preview.extra,
        }

    @staticmethod
    def _print_preview(preview: SourcePreview) -> None:
        console.print("[bold]Migration preview:[/bold]")
        console.print(f"  Documents:  {preview.doc_count}")
        if preview.dimensions:
            console.print(f"  Dimensions: {preview.dimensions}")
        if preview.metadata_fields:
            console.print(f"  Metadata:   {', '.join(preview.metadata_fields)}")
        if preview.extra:
            for k, v in preview.extra.items():
                console.print(f"  {k}: {v}")

    @staticmethod
    def _print_result(result: MigrationResult) -> None:
        console.print()
        console.print("[bold green]Migration complete.[/bold green]")
        console.print(f"  Source docs:  {result.source_doc_count}")
        console.print(f"  Migrated:     {result.migrated}")
        if result.failed:
            console.print(f"  [red]Failed:      {result.failed}[/red]")
        console.print(f"  Batches:      {result.batches}")
        console.print(f"  Elapsed:      {result.elapsed_seconds:.1f}s")
        if result.resumed_from is not None:
            console.print(f"  Resumed from: batch {result.resumed_from}")

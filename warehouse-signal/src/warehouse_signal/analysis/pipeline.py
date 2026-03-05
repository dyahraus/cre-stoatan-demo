"""Analysis pipeline: get unprocessed → extract signals → save → mark processed.

Mirrors the ingestion pipeline's async orchestration pattern.
"""

from __future__ import annotations

import asyncio

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from warehouse_signal.analysis.base import SignalAnalyzer
from warehouse_signal.config import Config
from warehouse_signal.models.schemas import TranscriptChunk
from warehouse_signal.storage.sqlite import Storage

console = Console()


async def analyze_transcript(
    analyzer: SignalAnalyzer,
    storage: Storage,
    transcript_row: dict,
) -> int:
    """Analyze all chunks for a single transcript. Returns count of extractions saved."""
    quarter_key = transcript_row["quarter_key"]
    ticker = transcript_row["ticker"]
    year = transcript_row["year"]
    quarter = transcript_row["quarter"]

    chunk_rows = storage.get_chunks_for_transcript(quarter_key)
    if not chunk_rows:
        storage.mark_processed(quarter_key)
        return 0

    company_name = storage.get_company_name(ticker)
    count = 0

    for row in chunk_rows:
        chunk = TranscriptChunk(
            chunk_id=row["chunk_id"],
            transcript_key=row["transcript_key"],
            chunk_index=row["chunk_index"],
            text=row["text"],
            section_type=row["section_type"],
            speaker=row.get("speaker"),
            speaker_role=row.get("speaker_role"),
            token_estimate=row.get("token_estimate", 0),
        )

        extraction = await analyzer.extract_signals(
            chunk, ticker, company_name, year, quarter
        )

        storage.save_extraction(
            chunk_id=chunk.chunk_id,
            transcript_key=quarter_key,
            model=analyzer.name,
            version=Config.EXTRACTION_VERSION,
            extraction=extraction,
        )
        count += 1

    storage.mark_processed(quarter_key)
    return count


async def analyze_all_unprocessed(
    analyzer: SignalAnalyzer,
    storage: Storage,
    concurrency: int | None = None,
) -> dict[str, int]:
    """Process all unprocessed transcripts. Returns {quarter_key: chunks_analyzed}."""
    max_concurrent = concurrency or Config.EXTRACTION_CONCURRENCY
    unprocessed = storage.get_unprocessed_transcripts(limit=500)

    if not unprocessed:
        console.print("[yellow]No unprocessed transcripts found.[/yellow]")
        return {}

    results: dict[str, int] = {}
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _analyze_one(row: dict):
        async with semaphore:
            try:
                count = await analyze_transcript(analyzer, storage, row)
                results[row["quarter_key"]] = count
            except Exception as e:
                console.print(f"  [red]✗[/red] {row['quarter_key']}: {e}")
                results[row["quarter_key"]] = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task(
            "Analyzing transcripts",
            total=len(unprocessed),
        )

        tasks = [_analyze_one(row) for row in unprocessed]

        for i in range(0, len(tasks), max_concurrent):
            batch = tasks[i : i + max_concurrent]
            await asyncio.gather(*batch)
            progress.advance(task, len(batch))

    return results


def print_analysis_summary(results: dict[str, int]) -> None:
    """Pretty-print analysis results."""
    total_transcripts = len(results)
    total_chunks = sum(results.values())
    analyzed = sum(1 for v in results.values() if v > 0)

    table = Table(title="Analysis Summary")
    table.add_column("Metric", style="bold")
    table.add_column("Count", justify="right")
    table.add_row("Transcripts processed", str(total_transcripts))
    table.add_row("With extractions", f"[green]{analyzed}[/green]")
    table.add_row("Total chunks analyzed", f"[cyan]{total_chunks}[/cyan]")
    console.print(table)

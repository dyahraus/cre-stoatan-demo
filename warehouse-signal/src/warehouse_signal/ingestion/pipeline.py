"""Ingestion pipeline: fetch → parse → chunk → store.

This is the main orchestration module that ties together the provider,
parser, and storage layers.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table

from warehouse_signal.ingestion.parser import chunk_transcript, parse_sections
from warehouse_signal.models.schemas import Transcript
from warehouse_signal.providers.base import TranscriptProvider
from warehouse_signal.storage.sqlite import Storage

console = Console()


async def ingest_transcript(
    provider: TranscriptProvider,
    storage: Storage,
    ticker: str,
    year: int,
    quarter: int,
    force: bool = False,
) -> Transcript | None:
    """Fetch, parse, chunk, and store a single transcript.

    Returns the Transcript if successfully ingested, None if skipped or failed.
    """
    # Skip if already stored (unless forced)
    if not force and storage.has_transcript(ticker, year, quarter):
        return None

    # Fetch from provider
    transcript = await provider.get_transcript(ticker, year, quarter)
    if not transcript:
        return None

    # Parse into sections (prepared remarks vs Q&A)
    parse_sections(transcript)

    # Chunk for LLM processing
    chunks = chunk_transcript(transcript)

    # Store
    storage.save_transcript(transcript)
    storage.save_chunks(chunks)

    return transcript


async def backfill_company(
    provider: TranscriptProvider,
    storage: Storage,
    ticker: str,
    max_quarters: int | None = None,
) -> int:
    """Backfill all available transcripts for a single company.

    Returns the number of newly ingested transcripts.
    """
    available = await provider.list_available_transcripts(ticker)
    if max_quarters:
        available = available[:max_quarters]

    ingested = 0
    for meta in available:
        result = await ingest_transcript(
            provider, storage, meta.ticker, meta.year, meta.quarter
        )
        if result:
            ingested += 1
            # Be polite to the API
            await asyncio.sleep(0.5)

    return ingested


async def ingest_universe(
    provider: TranscriptProvider,
    storage: Storage,
    tickers: list[str],
    year: int,
    quarter: int,
    concurrency: int = 5,
) -> dict[str, bool]:
    """Ingest a specific quarter for a list of tickers.

    Returns a dict of {ticker: success_bool}.
    """
    semaphore = asyncio.Semaphore(concurrency)
    results: dict[str, bool] = {}

    async def _ingest_one(ticker: str):
        async with semaphore:
            try:
                result = await ingest_transcript(
                    provider, storage, ticker, year, quarter
                )
                results[ticker] = result is not None
            except Exception as e:
                console.print(f"  [red]✗[/red] {ticker}: {e}")
                results[ticker] = False

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task(
            f"Ingesting {year}Q{quarter}",
            total=len(tickers),
        )

        tasks = []
        for ticker in tickers:
            tasks.append(_ingest_one(ticker))

        # Process in batches to avoid overwhelming the API
        for i in range(0, len(tasks), concurrency):
            batch = tasks[i : i + concurrency]
            await asyncio.gather(*batch)
            progress.advance(task, len(batch))

    return results


def print_ingestion_summary(results: dict[str, bool]) -> None:
    """Pretty-print ingestion results."""
    success = sum(1 for v in results.values() if v)
    skipped_or_failed = len(results) - success

    table = Table(title="Ingestion Summary")
    table.add_column("Metric", style="bold")
    table.add_column("Count", justify="right")
    table.add_row("Total tickers", str(len(results)))
    table.add_row("Newly ingested", f"[green]{success}[/green]")
    table.add_row("Skipped/Failed", f"[yellow]{skipped_or_failed}[/yellow]")
    console.print(table)

#!/usr/bin/env python3
"""CLI entry point for the warehouse signal ingestion pipeline.

Usage:
    # Ingest a single transcript
    python scripts/ingest.py --ticker PLD --year 2024 --quarter 3

    # Ingest latest quarter for all companies in universe
    python scripts/ingest.py --universe --year 2024 --quarter 4

    # Backfill all available transcripts for a company
    python scripts/ingest.py --ticker AMZN --backfill

    # Check what's in the database
    python scripts/ingest.py --stats

    # Run with a specific provider
    python scripts/ingest.py --provider mock --ticker PLD --year 2024 --quarter 3
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Ensure the src directory is on the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rich.console import Console
from rich.table import Table

from warehouse_signal.config import Config
from warehouse_signal.providers import get_provider
from warehouse_signal.storage.sqlite import Storage
from warehouse_signal.ingestion.pipeline import (
    backfill_company,
    ingest_transcript,
    ingest_universe,
    print_ingestion_summary,
)
from warehouse_signal.universe.sp500 import get_universe

console = Console()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Warehouse Signal — Earnings Transcript Ingestion"
    )
    parser.add_argument("--provider", type=str, default=None, help="Override transcript provider")
    parser.add_argument("--ticker", type=str, default=None, help="Single ticker to ingest")
    parser.add_argument("--year", type=int, default=None, help="Fiscal year")
    parser.add_argument("--quarter", type=int, choices=[1, 2, 3, 4], default=None, help="Fiscal quarter")
    parser.add_argument("--universe", action="store_true", help="Ingest for all companies in universe")
    parser.add_argument("--backfill", action="store_true", help="Backfill all available transcripts")
    parser.add_argument("--max-quarters", type=int, default=None, help="Max quarters to backfill per company")
    parser.add_argument("--concurrency", type=int, default=5, help="Max concurrent API requests")
    parser.add_argument("--force", action="store_true", help="Re-fetch even if already stored")
    parser.add_argument("--stats", action="store_true", help="Print database statistics")
    parser.add_argument("--setup", action="store_true", help="Initialize database and load company universe")
    return parser.parse_args()


async def cmd_setup(storage: Storage) -> None:
    """Initialize the database and load the company universe."""
    console.print("[bold]Setting up database and loading company universe...[/bold]")
    companies = await get_universe()
    count = storage.upsert_companies(companies)
    console.print(f"  Loaded [green]{count}[/green] companies into universe")
    _print_stats(storage)


async def cmd_single(args: argparse.Namespace, storage: Storage) -> None:
    """Ingest a single transcript."""
    if not args.ticker or not args.year or not args.quarter:
        console.print("[red]Error: --ticker, --year, and --quarter are required[/red]")
        return

    async with get_provider(args.provider) as provider:
        console.print(
            f"Fetching {args.ticker} {args.year}Q{args.quarter} "
            f"via [cyan]{provider.name}[/cyan]..."
        )
        result = await ingest_transcript(
            provider, storage, args.ticker, args.year, args.quarter, force=args.force
        )
        if result:
            console.print(f"  [green]✓[/green] Stored: {result.quarter_key}")
            console.print(f"    Sections: {len(result.sections)}")
            console.print(f"    Raw text length: {len(result.raw_text):,} chars")
        else:
            console.print(f"  [yellow]Skipped[/yellow] (already stored or not available)")


async def cmd_backfill(args: argparse.Namespace, storage: Storage) -> None:
    """Backfill all transcripts for a ticker."""
    if not args.ticker:
        console.print("[red]Error: --ticker is required for backfill[/red]")
        return

    async with get_provider(args.provider) as provider:
        console.print(
            f"Backfilling {args.ticker} via [cyan]{provider.name}[/cyan]..."
        )
        count = await backfill_company(
            provider, storage, args.ticker, max_quarters=args.max_quarters
        )
        console.print(f"  Ingested [green]{count}[/green] new transcripts")


async def cmd_universe_ingest(args: argparse.Namespace, storage: Storage) -> None:
    """Ingest a quarter for the full universe."""
    if not args.year or not args.quarter:
        console.print("[red]Error: --year and --quarter are required with --universe[/red]")
        return

    tickers = storage.get_active_tickers()
    if not tickers:
        console.print("[yellow]No companies in universe. Run --setup first.[/yellow]")
        return

    console.print(
        f"Ingesting {args.year}Q{args.quarter} for [cyan]{len(tickers)}[/cyan] companies..."
    )

    async with get_provider(args.provider) as provider:
        results = await ingest_universe(
            provider, storage, tickers, args.year, args.quarter,
            concurrency=args.concurrency,
        )
        print_ingestion_summary(results)


def _print_stats(storage: Storage) -> None:
    stats = storage.get_stats()
    table = Table(title="Database Statistics")
    table.add_column("Table", style="bold")
    table.add_column("Count", justify="right")
    for key, value in stats.items():
        table.add_row(key.replace("_", " ").title(), str(value))
    console.print(table)


async def main() -> None:
    args = parse_args()

    # Validate config
    issues = Config.validate()
    for issue in issues:
        console.print(f"[yellow]⚠ {issue}[/yellow]")

    storage = Storage()

    if args.stats:
        _print_stats(storage)
        return

    if args.setup:
        await cmd_setup(storage)
        return

    if args.backfill:
        await cmd_backfill(args, storage)
    elif args.universe:
        await cmd_universe_ingest(args, storage)
    elif args.ticker:
        await cmd_single(args, storage)
    else:
        console.print("[yellow]No action specified. Use --help to see options.[/yellow]")

    # Always show stats after an action
    _print_stats(storage)


if __name__ == "__main__":
    asyncio.run(main())

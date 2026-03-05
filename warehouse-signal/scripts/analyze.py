#!/usr/bin/env python3
"""CLI entry point for signal extraction, scoring, and deal radar.

Usage:
    # Extract signals from all unprocessed transcripts (mock analyzer)
    python scripts/analyze.py --extract

    # Extract using Claude API
    python scripts/analyze.py --extract --analyzer claude

    # Extract for a single company
    python scripts/analyze.py --extract --ticker PLD

    # Compute company-level scores
    python scripts/analyze.py --score

    # Show deal radar
    python scripts/analyze.py --radar

    # Filter radar by geography or sector
    python scripts/analyze.py --radar --geo US_Southeast --min-score 0.5

    # Company detail
    python scripts/analyze.py --detail PLD

    # Geography summary
    python scripts/analyze.py --geo-summary

    # Full pipeline: extract + score + radar
    python scripts/analyze.py --full-pipeline
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

from warehouse_signal.analysis import get_analyzer
from warehouse_signal.analysis.pipeline import (
    analyze_all_unprocessed,
    analyze_transcript,
    print_analysis_summary,
)
from warehouse_signal.config import Config
from warehouse_signal.models.schemas import CompanyScore, MoveType, Sector, TimeHorizon
from warehouse_signal.radar.alerts import RadarFilter, filter_scores
from warehouse_signal.radar.display import (
    display_company_detail,
    display_geo_summary,
    display_radar,
)
from warehouse_signal.scoring.aggregator import score_all_companies, score_company
from warehouse_signal.storage.sqlite import Storage

console = Console()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Warehouse Signal — Analysis, Scoring & Deal Radar"
    )
    # Extraction
    parser.add_argument("--extract", action="store_true", help="Run signal extraction on unprocessed transcripts")
    parser.add_argument("--analyzer", type=str, default=None, help="Analyzer backend (claude, mock)")
    parser.add_argument("--ticker", type=str, default=None, help="Limit extraction to a specific ticker")
    parser.add_argument("--concurrency", type=int, default=None, help="Max concurrent API calls")

    # Scoring
    parser.add_argument("--score", action="store_true", help="Compute company-level scores")

    # Radar
    parser.add_argument("--radar", action="store_true", help="Show deal radar")
    parser.add_argument("--detail", type=str, metavar="TICKER", help="Show detail for a company")
    parser.add_argument("--geo-summary", action="store_true", help="Show geography summary")
    parser.add_argument("--min-score", type=float, default=0.3, help="Minimum score for radar (default: 0.3)")
    parser.add_argument("--geo", type=str, default=None, help="Filter by geography")
    parser.add_argument("--sector", type=str, default=None, help="Filter by sector")
    parser.add_argument("--top-n", type=int, default=20, help="Number of results in radar")

    # Full pipeline
    parser.add_argument("--full-pipeline", action="store_true", help="Extract + Score + Radar")

    # Stats
    parser.add_argument("--stats", action="store_true", help="Print database statistics")

    return parser.parse_args()


async def cmd_extract(args: argparse.Namespace, storage: Storage) -> None:
    """Run signal extraction on unprocessed transcripts."""
    async with get_analyzer(args.analyzer) as analyzer:
        console.print(f"Running signal extraction via [cyan]{analyzer.name}[/cyan]...")

        if args.ticker:
            # Extract for a single ticker's unprocessed transcripts
            unprocessed = storage.get_unprocessed_transcripts(limit=500)
            ticker_rows = [r for r in unprocessed if r["ticker"] == args.ticker.upper()]
            if not ticker_rows:
                console.print(f"[yellow]No unprocessed transcripts for {args.ticker}[/yellow]")
                return
            results = {}
            for row in ticker_rows:
                count = await analyze_transcript(analyzer, storage, row)
                results[row["quarter_key"]] = count
                console.print(f"  [green]✓[/green] {row['quarter_key']}: {count} chunks")
        else:
            results = await analyze_all_unprocessed(
                analyzer, storage, concurrency=args.concurrency
            )

        print_analysis_summary(results)


async def cmd_score(storage: Storage) -> None:
    """Compute company-level scores."""
    console.print("[bold]Computing company scores...[/bold]")
    scores = score_all_companies(storage)
    if scores:
        console.print(f"  Scored [green]{len(scores)}[/green] companies")
        display_radar(scores[:10], title="Top 10 Companies by Expansion Score")
    else:
        console.print("[yellow]No signal extractions found. Run --extract first.[/yellow]")


async def cmd_radar(args: argparse.Namespace, storage: Storage) -> None:
    """Show deal radar with optional filters."""
    raw_scores = storage.get_all_company_scores()
    if not raw_scores:
        console.print("[yellow]No company scores found. Run --score first.[/yellow]")
        return

    scores = [storage.row_to_company_score(row) for row in raw_scores]

    # Build filter
    radar_filter = RadarFilter(
        min_score=args.min_score,
        top_n=args.top_n,
    )
    if args.geo:
        radar_filter.geographies = [args.geo]
    if args.sector:
        try:
            radar_filter.sectors = [Sector(args.sector)]
        except ValueError:
            console.print(f"[red]Unknown sector: {args.sector}[/red]")
            return

    filtered = filter_scores(scores, radar_filter)
    display_radar(filtered)


async def cmd_detail(ticker: str, storage: Storage) -> None:
    """Show detail for a single company."""
    score = score_company(storage, ticker.upper())
    if score:
        display_company_detail(score)
    else:
        console.print(f"[yellow]No extractions found for {ticker}[/yellow]")


async def cmd_geo_summary(storage: Storage) -> None:
    """Show geography summary."""
    raw_scores = storage.get_all_company_scores()
    if not raw_scores:
        console.print("[yellow]No company scores found. Run --score first.[/yellow]")
        return

    scores = [storage.row_to_company_score(r) for r in raw_scores]
    display_geo_summary(scores)


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

    if args.full_pipeline:
        await cmd_extract(args, storage)
        await cmd_score(storage)
        await cmd_radar(args, storage)
        return

    if args.extract:
        await cmd_extract(args, storage)
    if args.score:
        await cmd_score(storage)
    if args.radar:
        await cmd_radar(args, storage)
    if args.detail:
        await cmd_detail(args.detail, storage)
    if args.geo_summary:
        await cmd_geo_summary(storage)

    if not any([args.extract, args.score, args.radar, args.detail,
                args.geo_summary, args.full_pipeline, args.stats]):
        console.print("[yellow]No action specified. Use --help to see options.[/yellow]")


if __name__ == "__main__":
    asyncio.run(main())

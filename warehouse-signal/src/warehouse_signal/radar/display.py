"""Rich CLI display for deal radar, company detail, and geography summary."""

from __future__ import annotations

import json
from collections import Counter

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from warehouse_signal.models.schemas import CompanyScore

console = Console()


def display_radar(scores: list[CompanyScore], title: str = "Deal Radar") -> None:
    """Display ranked company expansion scores as a table."""
    if not scores:
        console.print("[yellow]No companies match the current filter.[/yellow]")
        return

    table = Table(title=title)
    table.add_column("Rank", justify="right", style="dim", width=4)
    table.add_column("Ticker", style="bold cyan", width=6)
    table.add_column("Company", width=24)
    table.add_column("Score", justify="right", style="bold", width=6)
    table.add_column("Move", width=13)
    table.add_column("Horizon", width=11)
    table.add_column("Geographies", width=30)
    table.add_column("Signals", width=14)

    for i, s in enumerate(scores, 1):
        # Color-code score
        score_str = f"{s.composite_score:.2f}"
        if s.composite_score >= 0.7:
            score_str = f"[green]{score_str}[/green]"
        elif s.composite_score >= 0.4:
            score_str = f"[yellow]{score_str}[/yellow]"
        else:
            score_str = f"[dim]{score_str}[/dim]"

        # Signal flags as compact icons
        flags = []
        if s.has_capex_signal:
            flags.append("capex")
        if s.has_build_to_suit:
            flags.append("BTS")
        if s.has_last_mile:
            flags.append("LM")
        flags_str = ", ".join(flags) if flags else "-"

        geo_str = ", ".join(s.top_geographies[:3]) if s.top_geographies else "-"

        table.add_row(
            str(i),
            s.ticker,
            s.company_name[:24],
            score_str,
            s.dominant_move_type.value,
            s.dominant_time_horizon.value,
            geo_str,
            flags_str,
        )

    console.print(table)


def display_company_detail(score: CompanyScore) -> None:
    """Display detailed panel for a single company."""
    lines = []
    lines.append(f"[bold]Composite Score:[/bold] [green]{score.composite_score:.3f}[/green]")
    lines.append(
        f"[bold]Expansion Score:[/bold] avg={score.avg_expansion_score:.2f}  "
        f"max={score.max_expansion_score:.2f}"
    )
    lines.append(
        f"[bold]Relevance:[/bold] avg={score.avg_warehouse_relevance:.2f}  "
        f"relevant chunks={score.num_relevant_chunks}/{score.total_chunks}"
    )
    lines.append(f"[bold]Move Type:[/bold] {score.dominant_move_type.value}")
    lines.append(f"[bold]Time Horizon:[/bold] {score.dominant_time_horizon.value}")

    # Signal flags
    flags = []
    if score.has_capex_signal:
        flags.append("[green]capex_expansion[/green]")
    if score.has_build_to_suit:
        flags.append("[green]build_to_suit[/green]")
    if score.has_last_mile:
        flags.append("[green]last_mile[/green]")
    lines.append(f"[bold]Signals:[/bold] {', '.join(flags) if flags else '[dim]none[/dim]'}")

    # Geographies
    geo_str = ", ".join(score.top_geographies) if score.top_geographies else "none detected"
    lines.append(f"[bold]Geographies:[/bold] {geo_str}")

    # Evidence
    if score.evidence_snippets:
        lines.append("")
        lines.append("[bold]Evidence:[/bold]")
        for snippet in score.evidence_snippets:
            lines.append(f'  [dim]"[/dim]{snippet[:120]}[dim]"[/dim]')

    # Transcripts
    lines.append("")
    lines.append(f"[bold]Transcripts:[/bold] {', '.join(score.transcript_keys)}")

    panel = Panel(
        "\n".join(lines),
        title=f"{score.ticker}: {score.company_name} ({score.sector.value})",
        border_style="cyan",
    )
    console.print(panel)


def display_geo_summary(scores: list[CompanyScore]) -> None:
    """Display geography summary aggregated across all scored companies."""
    geo_data: dict[str, list[float]] = {}
    geo_companies: dict[str, set[str]] = {}

    for s in scores:
        for geo in s.top_geographies:
            geo_data.setdefault(geo, []).append(s.composite_score)
            geo_companies.setdefault(geo, set()).add(s.ticker)

    if not geo_data:
        console.print("[yellow]No geographic data available.[/yellow]")
        return

    table = Table(title="Geographic Heatmap")
    table.add_column("Region", style="bold", width=22)
    table.add_column("Companies", justify="right", width=10)
    table.add_column("Avg Score", justify="right", width=10)
    table.add_column("Max Score", justify="right", width=10)
    table.add_column("Tickers", width=30)

    # Sort by average score descending
    sorted_geos = sorted(
        geo_data.keys(),
        key=lambda g: sum(geo_data[g]) / len(geo_data[g]),
        reverse=True,
    )

    for geo in sorted_geos:
        scores_list = geo_data[geo]
        avg = sum(scores_list) / len(scores_list)
        mx = max(scores_list)
        tickers = ", ".join(sorted(geo_companies[geo]))

        avg_str = f"{avg:.2f}"
        if avg >= 0.7:
            avg_str = f"[green]{avg_str}[/green]"
        elif avg >= 0.4:
            avg_str = f"[yellow]{avg_str}[/yellow]"

        table.add_row(
            geo,
            str(len(geo_companies[geo])),
            avg_str,
            f"{mx:.2f}",
            tickers[:30],
        )

    console.print(table)

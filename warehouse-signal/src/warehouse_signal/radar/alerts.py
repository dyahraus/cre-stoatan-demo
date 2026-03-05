"""Radar filtering for deal alerts."""

from __future__ import annotations

from dataclasses import dataclass, field

from warehouse_signal.models.schemas import (
    CompanyScore,
    MoveType,
    Sector,
    TimeHorizon,
)


@dataclass
class RadarFilter:
    """Configuration for deal radar filtering."""
    min_score: float = 0.3
    sectors: list[Sector] | None = None
    geographies: list[str] | None = None
    move_types: list[MoveType] | None = None
    time_horizons: list[TimeHorizon] | None = None
    top_n: int = 20


def filter_scores(
    scores: list[CompanyScore], f: RadarFilter
) -> list[CompanyScore]:
    """Apply radar filter to a list of CompanyScores."""
    results = [s for s in scores if s.composite_score >= f.min_score]

    if f.sectors:
        results = [s for s in results if s.sector in f.sectors]

    if f.geographies:
        results = [
            s for s in results
            if any(g in s.top_geographies for g in f.geographies)
        ]

    if f.move_types:
        results = [s for s in results if s.dominant_move_type in f.move_types]

    if f.time_horizons:
        results = [s for s in results if s.dominant_time_horizon in f.time_horizons]

    # Already sorted by score from score_all_companies
    return results[:f.top_n]

"""Tests for radar filtering."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from warehouse_signal.models.schemas import (
    CompanyScore,
    MoveType,
    Sector,
    TimeHorizon,
)
from warehouse_signal.radar.alerts import RadarFilter, filter_scores


def _make_score(
    ticker: str,
    score: float,
    sector: Sector = Sector.OTHER,
    geos: list[str] | None = None,
    move: MoveType = MoveType.EXPANSION,
    horizon: TimeHorizon = TimeHorizon.NEAR_TERM,
) -> CompanyScore:
    return CompanyScore(
        ticker=ticker,
        company_name=f"{ticker} Corp",
        sector=sector,
        composite_score=score,
        top_geographies=geos or [],
        dominant_move_type=move,
        dominant_time_horizon=horizon,
    )


@pytest.fixture
def sample_scores() -> list[CompanyScore]:
    return [
        _make_score("PLD", 0.91, Sector.REIT_INDUSTRIAL, ["Inland_Empire", "Dallas_Fort_Worth"]),
        _make_score("AMZN", 0.87, Sector.ECOMMERCE, ["US_Southeast", "Indianapolis"]),
        _make_score("WMT", 0.72, Sector.RETAIL, ["US_Midwest"]),
        _make_score("HD", 0.45, Sector.RETAIL, ["US_Southeast"]),
        _make_score("AAPL", 0.15, Sector.OTHER, []),
    ]


def test_filter_by_min_score(sample_scores):
    f = RadarFilter(min_score=0.5)
    results = filter_scores(sample_scores, f)
    assert len(results) == 3
    assert all(s.composite_score >= 0.5 for s in results)


def test_filter_by_geography(sample_scores):
    f = RadarFilter(min_score=0.0, geographies=["US_Southeast"])
    results = filter_scores(sample_scores, f)
    assert len(results) == 2
    tickers = {s.ticker for s in results}
    assert "AMZN" in tickers
    assert "HD" in tickers


def test_filter_by_sector(sample_scores):
    f = RadarFilter(min_score=0.0, sectors=[Sector.RETAIL])
    results = filter_scores(sample_scores, f)
    assert len(results) == 2
    assert all(s.sector == Sector.RETAIL for s in results)


def test_filter_top_n(sample_scores):
    f = RadarFilter(min_score=0.0, top_n=2)
    results = filter_scores(sample_scores, f)
    assert len(results) == 2


def test_filter_combined(sample_scores):
    f = RadarFilter(
        min_score=0.4,
        sectors=[Sector.RETAIL],
        geographies=["US_Southeast"],
    )
    results = filter_scores(sample_scores, f)
    assert len(results) == 1
    assert results[0].ticker == "HD"


def test_filter_no_matches(sample_scores):
    f = RadarFilter(min_score=0.99)
    results = filter_scores(sample_scores, f)
    assert len(results) == 0

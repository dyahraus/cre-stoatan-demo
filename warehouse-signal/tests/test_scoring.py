"""Tests for scoring aggregation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from warehouse_signal.analysis.mock import MockAnalyzer
from warehouse_signal.analysis.pipeline import analyze_transcript
from warehouse_signal.ingestion.pipeline import ingest_transcript
from warehouse_signal.models.schemas import MoveType, TimeHorizon
from warehouse_signal.providers.mock import MockProvider
from warehouse_signal.scoring.aggregator import (
    compute_composite_score,
    score_all_companies,
    score_company,
)
from warehouse_signal.storage.sqlite import Storage


@pytest.fixture
def provider():
    return MockProvider()


@pytest.fixture
def analyzer():
    return MockAnalyzer()


@pytest.fixture
def storage(tmp_path):
    return Storage(db_path=tmp_path / "test.db")


# ---------------------------------------------------------------------------
# Composite score tests
# ---------------------------------------------------------------------------

def test_composite_score_high():
    extractions = [
        {
            "warehouse_relevance": 0.9,
            "expansion_score": 0.85,
            "time_horizon": "near_term",
            "signals_json": json.dumps({
                "signals": {"capex_expansion": True, "build_to_suit": True, "last_mile_expansion": False}
            }),
        },
        {
            "warehouse_relevance": 0.7,
            "expansion_score": 0.6,
            "time_horizon": "immediate",
            "signals_json": json.dumps({
                "signals": {"capex_expansion": False, "build_to_suit": False, "last_mile_expansion": True}
            }),
        },
    ]
    score = compute_composite_score(extractions)
    assert score > 0.5


def test_composite_score_zero_when_no_relevant():
    extractions = [
        {
            "warehouse_relevance": 0.1,
            "expansion_score": 0.0,
            "time_horizon": "unspecified",
            "signals_json": json.dumps({"signals": {}}),
        },
    ]
    score = compute_composite_score(extractions)
    assert score == 0.0


def test_composite_score_empty():
    assert compute_composite_score([]) == 0.0


def test_composite_score_mixed():
    extractions = [
        {
            "warehouse_relevance": 0.8,
            "expansion_score": 0.7,
            "time_horizon": "near_term",
            "signals_json": json.dumps({"signals": {"capex_expansion": True}}),
        },
        {
            "warehouse_relevance": 0.1,
            "expansion_score": 0.0,
            "time_horizon": "unspecified",
            "signals_json": json.dumps({"signals": {}}),
        },
        {
            "warehouse_relevance": 0.4,
            "expansion_score": 0.3,
            "time_horizon": "long_term",
            "signals_json": json.dumps({"signals": {}}),
        },
    ]
    score = compute_composite_score(extractions)
    # Should be moderate — one high signal + one low relevant + one irrelevant
    assert 0.2 < score < 0.8


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_score_company_integration(provider, analyzer, storage):
    """Full pipeline: ingest → analyze → score → verify."""
    # Ingest
    await ingest_transcript(provider, storage, "PLD", 2024, 3)
    unprocessed = storage.get_unprocessed_transcripts()
    await analyze_transcript(analyzer, storage, unprocessed[0])

    # Score
    score = score_company(storage, "PLD")
    assert score is not None
    assert score.ticker == "PLD"
    assert score.composite_score > 0
    assert score.total_chunks > 0


@pytest.mark.asyncio
async def test_score_all_companies(provider, analyzer, storage):
    """Score multiple companies, verify sorted descending."""
    for ticker in ["PLD", "AMZN", "HD"]:
        await ingest_transcript(provider, storage, ticker, 2024, 3)

    unprocessed = storage.get_unprocessed_transcripts()
    for row in unprocessed:
        await analyze_transcript(analyzer, storage, row)

    scores = score_all_companies(storage)
    assert len(scores) >= 2  # at least high + moderate signal companies

    # Verify descending sort
    for i in range(len(scores) - 1):
        assert scores[i].composite_score >= scores[i + 1].composite_score

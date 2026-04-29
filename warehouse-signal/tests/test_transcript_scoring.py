"""Per-transcript hybrid scoring + tier mapping tests."""

from __future__ import annotations

import pathlib
import tempfile

import pytest

from warehouse_signal.analysis.keyword_engine import detect
from warehouse_signal.models.schemas import (
    ChunkExtraction,
    Company,
    MoveType,
    Sector,
    SectionType,
    SignalFlags,
    SignalTier,
    TimeHorizon,
    Transcript,
    TranscriptChunk,
    TranscriptMetadata,
)
from warehouse_signal.scoring.aggregator import (
    compute_chunk_score,
    score_company,
    score_transcript,
)
from warehouse_signal.scoring.tiers import tier_for_score
from warehouse_signal.storage.sqlite import Storage


@pytest.fixture
def storage():
    with tempfile.TemporaryDirectory() as d:
        path = pathlib.Path(d) / "ws.db"
        yield Storage(path)


def _seed(
    storage: Storage,
    *,
    ticker: str,
    text: str,
    relevance: float,
    expansion: float,
    flags: SignalFlags | None = None,
    time_horizon: TimeHorizon = TimeHorizon.NEAR_TERM,
    year: int = 2024,
    quarter: int = 3,
) -> str:
    quarter_key = f"{ticker}_{year}Q{quarter}"
    storage.upsert_company(
        Company(ticker=ticker, name=ticker, sector=Sector.REIT_INDUSTRIAL)
    )
    transcript = Transcript(
        metadata=TranscriptMetadata(
            ticker=ticker, year=year, quarter=quarter, provider="test"
        ),
        raw_text=text,
        sections=[],
    )
    storage.save_transcript(transcript)
    chunk = TranscriptChunk(
        chunk_id=f"{quarter_key}_c0",
        transcript_key=quarter_key,
        chunk_index=0,
        text=text,
        section_type=SectionType.PREPARED_REMARKS,
        token_estimate=len(text.split()),
    )
    storage.save_chunks([chunk])
    storage.save_extraction(
        chunk.chunk_id,
        quarter_key,
        "test",
        "v1.0",
        ChunkExtraction(
            warehouse_relevance=relevance,
            expansion_score=expansion,
            move_type=MoveType.EXPANSION,
            time_horizon=time_horizon,
            signals=flags or SignalFlags(),
        ),
    )
    fw = storage.get_default_framework()
    hits = detect(chunk, fw)
    storage.replace_keyword_hits_for_chunk(chunk.chunk_id, hits)
    return quarter_key


def test_strong_pld_passage_scores_strong_tier(storage):
    text = (
        "We broke ground on two new distribution centers — committed 180 million "
        "in capex. We have committed 2.4 million sq ft of new fulfillment center "
        "capacity. Three build-to-suit projects under letter of intent for Q3 2026."
    )
    qk = _seed(
        storage,
        ticker="PLD",
        text=text,
        relevance=0.9,
        expansion=0.85,
        flags=SignalFlags(capex_expansion=True, build_to_suit=True),
    )
    fw = storage.get_default_framework()
    score = score_transcript(storage, qk, fw)
    assert score is not None
    assert score.composite_score >= 0.5
    # Tier should be at least Moderate (Strong if everything aligns)
    assert score.tier in (SignalTier.STRONG, SignalTier.MODERATE)
    # Components are all populated
    c = score.score_components
    assert c.max_expansion > 0 and c.weighted_avg > 0
    assert c.keyword_component > 0 and c.commitment_component > 0
    assert score.confidence > 0


def test_pure_financial_passage_scores_noise(storage):
    text = (
        "Revenue grew 6 percent year over year. Operating expenses were well "
        "controlled at 22 percent of revenue. We returned 350 million to "
        "shareholders this quarter through dividends and buybacks."
    )
    qk = _seed(
        storage,
        ticker="ZZZ",
        text=text,
        relevance=0.05,
        expansion=0.0,
    )
    fw = storage.get_default_framework()
    score = score_transcript(storage, qk, fw)
    assert score is not None
    assert score.composite_score == 0.0
    assert score.tier is SignalTier.NOISE


def test_keyword_only_chunks_still_relevant(storage):
    """A chunk with strong keywords but mediocre LLM relevance must still
    contribute to the composite via the keyword override."""
    text = (
        "We broke ground on two distribution centers and committed 180 million "
        "in logistics capex over the next 18 months. Letter of intent for Q3 2026."
    )
    qk = _seed(
        storage,
        ticker="KWO",
        text=text,
        relevance=0.1,  # below 0.3 threshold
        expansion=0.2,
    )
    fw = storage.get_default_framework()
    score = score_transcript(storage, qk, fw)
    assert score is not None
    # Despite low LLM relevance, keyword hits should rescue this chunk.
    assert score.num_relevant_chunks == 1
    assert score.composite_score > 0


def test_tier_mapping_boundaries():
    assert tier_for_score(0.0) is SignalTier.NOISE
    assert tier_for_score(0.24) is SignalTier.NOISE
    assert tier_for_score(0.25) is SignalTier.WATCHLIST
    assert tier_for_score(0.49) is SignalTier.WATCHLIST
    assert tier_for_score(0.50) is SignalTier.MODERATE
    assert tier_for_score(0.74) is SignalTier.MODERATE
    assert tier_for_score(0.75) is SignalTier.STRONG
    assert tier_for_score(1.0) is SignalTier.STRONG


def test_hybrid_chunk_score_weights():
    """Document the four-channel hybrid math: 0.40 LLM + 0.25 kw +
    0.20 concept + 0.15 commitment."""
    # No hits → score is purely the LLM term at 40%
    score, kw, commit, concept = compute_chunk_score(0.5, [])
    assert score == round(0.40 * 0.5, 4)
    assert kw == 0.0 and commit == 0.0 and concept == 0.0


def test_company_score_uses_latest_transcript(storage):
    """When a ticker has multiple transcripts, the latest drives the
    company-level tier."""
    text = (
        "We broke ground on two new distribution centers and committed 180 million "
        "in capex. Build-to-suit under letter of intent for Q3 2026."
    )
    fw = storage.get_default_framework()

    # Quarter 1 — moderate signal
    qk1 = _seed(
        storage,
        ticker="MULTI",
        text="Network optimization study underway. Capacity constraints flagged.",
        relevance=0.5,
        expansion=0.4,
        year=2024,
        quarter=1,
    )
    score1 = score_transcript(storage, qk1, fw)
    storage.save_transcript_score(score1)

    # Quarter 3 — strong signal
    qk3 = _seed(
        storage,
        ticker="MULTI",
        text=text,
        relevance=0.9,
        expansion=0.85,
        flags=SignalFlags(capex_expansion=True, build_to_suit=True),
        year=2024,
        quarter=3,
    )
    score3 = score_transcript(storage, qk3, fw)
    storage.save_transcript_score(score3)

    company = score_company(storage, "MULTI")
    assert company is not None
    # Company composite should match the most recent (Q3) transcript
    assert company.composite_score == score3.composite_score
    assert company.tier == score3.tier
    assert qk1 in company.transcript_keys
    assert qk3 in company.transcript_keys

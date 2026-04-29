"""Keyword engine unit tests."""

from __future__ import annotations

import math

from warehouse_signal.analysis.keyword_engine import (
    SATURATION_K,
    commitment_evidence_bonus,
    detect,
    hits_summary_by_category,
    keyword_score,
)
from warehouse_signal.models.schemas import (
    KeywordCategory,
    SectionType,
    SignalFramework,
    SignalKeyword,
    TranscriptChunk,
)
from warehouse_signal.scoring.tiers import DEFAULT_FRAMEWORK_SEED


def _chunk(text: str) -> TranscriptChunk:
    return TranscriptChunk(
        chunk_id="t",
        transcript_key="TKR_2024Q1",
        chunk_index=0,
        text=text,
        section_type=SectionType.PREPARED_REMARKS,
        token_estimate=len(text.split()),
    )


def test_detect_strong_pld_passage_hits_all_three_categories():
    fw = DEFAULT_FRAMEWORK_SEED()
    text = (
        "We broke ground on two new distribution centers — committed approximately "
        "180 million in logistics capex over the next 18 months. We have committed "
        "to adding 2.4 million sq ft of new fulfillment center capacity. Three "
        "build-to-suit projects are under letter of intent for Q3 2026. Capacity "
        "constraints across our network drove our network optimization study."
    )
    hits = detect(_chunk(text), fw)
    summary = hits_summary_by_category(hits)
    assert summary.get("commitment_level", 0) >= 2
    assert summary.get("industrial_transformation", 0) >= 2
    assert summary.get("supply_chain", 0) >= 1
    # Plurals match too
    phrases = {h.phrase for h in hits}
    assert "distribution center" in phrases


def test_detect_low_signal_passage_returns_no_hits():
    fw = DEFAULT_FRAMEWORK_SEED()
    text = (
        "Revenue grew 6 percent. Operating expenses well controlled at 22 percent "
        "of revenue. We returned 350 million to shareholders this quarter."
    )
    hits = detect(_chunk(text), fw)
    assert hits == []


def test_commitment_companion_required():
    """A commitment phrase without a numeric/date companion should not fire."""
    fw = DEFAULT_FRAMEWORK_SEED()
    text = "We may explore options at some point. We could grow into new spaces."
    hits = detect(_chunk(text), fw)
    # No companion → commitment hits filtered out
    commitment_hits = [
        h for h in hits if h.category == KeywordCategory.COMMITMENT_LEVEL
    ]
    assert commitment_hits == []


def test_keyword_score_saturates_monotonically():
    """As we keep adding hits, the score increases but never exceeds 1."""
    from warehouse_signal.models.schemas import KeywordHit

    def synth_hits(n: int, weight: float = 5.0) -> list[KeywordHit]:
        return [
            KeywordHit(
                keyword_id="k",
                chunk_id="c",
                transcript_key="t",
                category=KeywordCategory.INDUSTRIAL_TRANSFORMATION,
                phrase="x",
                match_text="x",
                match_offset=i,
                weight_contribution=weight,
            )
            for i in range(n)
        ]

    s_one = keyword_score(synth_hits(1))
    s_five = keyword_score(synth_hits(5))
    s_twenty = keyword_score(synth_hits(20))
    assert 0 < s_one < s_five < s_twenty <= 1.0
    # Saturation ~ 1 - exp(-Σw / K)
    expected = 1 - math.exp(-1 * 5.0 / SATURATION_K)
    assert abs(s_one - round(expected, 4)) < 1e-3


def test_commitment_bonus_ignores_other_categories():
    fw = DEFAULT_FRAMEWORK_SEED()
    # Pure industrial keyword passage with no commitment language
    text = "We use automation and robotics across our distribution centers."
    hits = detect(_chunk(text), fw)
    assert keyword_score(hits) > 0
    assert commitment_evidence_bonus(hits) == 0.0


def test_user_added_keyword_fires():
    fw = SignalFramework(
        id="custom",
        name="custom",
        keywords=[
            SignalKeyword(
                id="k1",
                framework_id="custom",
                category=KeywordCategory.SUPPLY_CHAIN,
                phrase="forklift density",
                weight=4.0,
            )
        ],
    )
    text = "Our forklift density is up 12% across the network this quarter."
    hits = detect(_chunk(text), fw)
    assert len(hits) == 1
    assert hits[0].match_text.lower() == "forklift density"

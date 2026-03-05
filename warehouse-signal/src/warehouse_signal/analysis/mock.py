"""Mock signal analyzer for testing and development.

Uses keyword matching to produce deterministic extractions without API calls.
"""

from __future__ import annotations

import re

from warehouse_signal.analysis.base import SignalAnalyzer
from warehouse_signal.models.schemas import (
    ChunkExtraction,
    GeographicMention,
    MoveType,
    Sentiment,
    SentimentDirection,
    SignalFlags,
    TimeHorizon,
    TranscriptChunk,
)

_WAREHOUSE_KEYWORDS = [
    "warehouse", "distribution center", "logistics", "fulfillment",
    "square feet", "sq ft", " dc ", "facility", "last mile", "build-to-suit",
    "build to suit", "capex", "broke ground", "groundbreaking",
]

_GEO_PATTERNS = {
    "Inland_Empire": re.compile(r"inland empire", re.IGNORECASE),
    "Indianapolis": re.compile(r"indianapolis", re.IGNORECASE),
    "Dallas_Fort_Worth": re.compile(r"dallas|fort worth|dfw", re.IGNORECASE),
    "US_Southeast": re.compile(r"southeast|south east", re.IGNORECASE),
    "US_Midwest": re.compile(r"midwest|mid-west", re.IGNORECASE),
}


class MockAnalyzer(SignalAnalyzer):
    """Deterministic mock analyzer using keyword matching."""

    @property
    def name(self) -> str:
        return "mock"

    async def extract_signals(
        self,
        chunk: TranscriptChunk,
        ticker: str,
        company_name: str,
        year: int,
        quarter: int,
    ) -> ChunkExtraction:
        text_lower = chunk.text.lower()

        # Count keyword hits
        hits = sum(1 for kw in _WAREHOUSE_KEYWORDS if kw in text_lower)
        relevance = min(hits / 5, 1.0)
        expansion = min(hits / 7, 1.0)

        # Detect geographic mentions
        geo_mentions = []
        for region, pattern in _GEO_PATTERNS.items():
            if pattern.search(chunk.text):
                geo_mentions.append(
                    GeographicMention(region=region, confidence=0.8, context="keyword match")
                )

        # Determine move type
        move_type = MoveType.UNKNOWN
        if hits >= 3:
            move_type = MoveType.EXPANSION
        elif hits >= 1:
            move_type = MoveType.OPTIMIZATION

        # Determine time horizon
        time_horizon = TimeHorizon.UNSPECIFIED
        if any(w in text_lower for w in ["next year", "next quarter", "q3", "q4"]):
            time_horizon = TimeHorizon.NEAR_TERM
        elif any(w in text_lower for w in ["broke ground", "committed", "under construction"]):
            time_horizon = TimeHorizon.IMMEDIATE

        # Signal flags
        signals = SignalFlags(
            capex_expansion="capex" in text_lower or "capital" in text_lower,
            demand_strength="increasing" if "demand" in text_lower and hits >= 2 else "stable",
            build_to_suit="build-to-suit" in text_lower or "build to suit" in text_lower,
            last_mile_expansion="last mile" in text_lower or "last-mile" in text_lower,
            automation_investment="robot" in text_lower or "automation" in text_lower,
            network_redesign="network" in text_lower and "redesign" in text_lower,
            construction_pipeline="active" if "construction" in text_lower else "none",
        )

        # Extract first sentence as evidence
        sentences = chunk.text.strip().split(".")
        evidence = (sentences[0] + ".").strip() if sentences else ""

        return ChunkExtraction(
            warehouse_relevance=round(relevance, 2),
            expansion_score=round(expansion, 2),
            move_type=move_type,
            time_horizon=time_horizon,
            sentiment=Sentiment(
                polarity=round(relevance * 0.8, 2),
                intensity="high" if relevance > 0.7 else "moderate" if relevance > 0.3 else "low",
                direction=SentimentDirection.POSITIVE if relevance > 0.3 else SentimentDirection.NEUTRAL,
            ),
            geographic_mentions=geo_mentions,
            signals=signals,
            evidence_quote=evidence[:200],
            reasoning=f"Keyword hits: {hits}/{len(_WAREHOUSE_KEYWORDS)}",
        )

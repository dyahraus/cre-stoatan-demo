"""Tier mapping + default keyword framework seed.

The four-tier output is the user-facing translation of the 0..1 composite.
Brokers should never read a bare number without seeing one of these labels.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from warehouse_signal.models.schemas import (
    KeywordCategory,
    SignalFramework,
    SignalKeyword,
    SignalTier,
)


# ---------------------------------------------------------------------------
# Tier mapping
# ---------------------------------------------------------------------------

# Lower bounds for each tier — `composite_score >= bound` ⇒ that tier.
# Order: highest tier first.
TIER_BOUNDS: list[tuple[SignalTier, float]] = [
    (SignalTier.STRONG, 0.75),
    (SignalTier.MODERATE, 0.50),
    (SignalTier.WATCHLIST, 0.25),
    (SignalTier.NOISE, 0.0),
]


# Plain-English description shown to users on each tier badge.
TIER_DESCRIPTION: dict[SignalTier, str] = {
    SignalTier.STRONG: (
        "Specific, committed plans with dollar amounts, square footage, "
        "or groundbreaking dates."
    ),
    SignalTier.MODERATE: (
        "Substantive discussion: network study underway, real estate team "
        "engaged, capacity constraints flagged."
    ),
    SignalTier.WATCHLIST: (
        "Early signals or qualified statements; track for future quarters."
    ),
    SignalTier.NOISE: (
        "No actionable warehouse expansion signal in this transcript."
    ),
}


def tier_for_score(score: float) -> SignalTier:
    """Map a 0..1 composite score to its plain-English tier."""
    for tier, bound in TIER_BOUNDS:
        if score >= bound:
            return tier
    return SignalTier.NOISE


# ---------------------------------------------------------------------------
# Default seed framework
# ---------------------------------------------------------------------------

# Weights are 1..10 (user-editable in the framework UI).
# Companion patterns must match within ~20 tokens of the keyword.

_NUMERIC_COMPANION = (
    r"(?:\$\s?\d|\d[\d,\.]*\s*(?:million|billion|m\b|b\b|sf\b|sq\.?\s?ft|"
    r"square\s+feet|square\s+foot|facilit|center|location|warehouse)|"
    r"q[1-4]\s*20\d{2}|20\d{2})"
)


def _seed_keyword(
    framework_id: str,
    category: KeywordCategory,
    phrase: str,
    weight: float,
    *,
    is_regex: bool = False,
    companion_pattern: str | None = None,
    notes: str = "",
) -> SignalKeyword:
    return SignalKeyword(
        id=str(uuid.uuid4()),
        framework_id=framework_id,
        category=category,
        phrase=phrase,
        is_regex=is_regex,
        weight=weight,
        companion_pattern=companion_pattern,
        notes=notes,
        created_at=datetime.now(timezone.utc),
    )


def DEFAULT_FRAMEWORK_SEED() -> SignalFramework:
    """Return the seed framework that ships on first DB init.

    Editable in the UI; this is just the starting point.
    """
    fid = "default"

    industrial = [
        ("automation", 5.0),
        ("robotics", 5.0),
        ("build-to-suit", 8.0),
        ("greenfield", 7.0),
        ("fulfillment center", 7.0),
        ("distribution center", 6.0),
        (r"\bDC\b", 4.0),  # disambiguate from "Washington DC" via case
        ("cross-dock", 6.0),
        ("goods-to-person", 5.0),
        ("regional fulfillment", 7.0),
        ("last-mile", 6.0),
        ("nearshoring", 7.0),
        ("reshoring", 7.0),
    ]

    supply = [
        ("network optimization", 6.0),
        ("network configuration", 5.0),
        ("network study", 7.0),
        ("consolidation", 5.0),
        ("capacity constraints", 7.0),
        ("utilization", 4.0),
        ("throughput", 4.0),
        ("inventory repositioning", 6.0),
        ("logistics footprint", 6.0),
        ("supply chain", 3.0),
    ]

    commitment_high = [
        ("broke ground", 9.0),
        ("groundbreaking", 9.0),
        ("under construction", 8.0),
        ("letter of intent", 8.0),
        ("we will", 4.0),
        ("we have committed", 9.0),
        ("we are committing", 9.0),
        ("approved capex", 9.0),
    ]
    commitment_medium = [
        ("we plan to", 6.0),
        ("we expect to", 5.0),
        ("evaluating", 4.0),
        ("are considering", 4.0),
    ]
    commitment_low = [
        ("we may", 2.0),
        ("we could", 2.0),
        ("potentially", 2.0),
        ("exploring options", 3.0),
    ]

    keywords: list[SignalKeyword] = []
    for phrase, w in industrial:
        is_regex = phrase.startswith(r"\b") or phrase.startswith("(")
        keywords.append(
            _seed_keyword(
                fid,
                KeywordCategory.INDUSTRIAL_TRANSFORMATION,
                phrase,
                w,
                is_regex=is_regex,
            )
        )
    for phrase, w in supply:
        keywords.append(
            _seed_keyword(fid, KeywordCategory.SUPPLY_CHAIN, phrase, w)
        )
    # Commitment keywords require a $/sqft/date companion within window
    for phrase, w in commitment_high + commitment_medium + commitment_low:
        keywords.append(
            _seed_keyword(
                fid,
                KeywordCategory.COMMITMENT_LEVEL,
                phrase,
                w,
                companion_pattern=_NUMERIC_COMPANION,
                notes="Requires a $ amount, sqft, facility count, or date nearby.",
            )
        )

    return SignalFramework(
        id=fid,
        name="Industrial Signal Default",
        description=(
            "Starter framework covering industrial transformation keywords, "
            "supply-chain language, and commitment-level classifiers. "
            "Edit weights and add phrases in the Framework page."
        ),
        is_default=True,
        keywords=keywords,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

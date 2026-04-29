"""Keyword detection engine — deterministic, citable, user-tunable.

Runs every keyword in a SignalFramework against a chunk of text. Returns
KeywordHit records (one per match) and a normalized 0..1 score derived
from the sum of matched weights.

This engine is decoupled from the LLM. The hybrid composite formula
(see scoring.aggregator) blends LLM expansion_score with keyword_score
so every contribution is traceable to either an LLM rationale or a
literal regex match in the transcript.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from warehouse_signal.models.schemas import (
    KeywordCategory,
    KeywordHit,
    SignalFramework,
    SignalKeyword,
    TranscriptChunk,
)

# Sliding window (in tokens) within which a companion pattern must match
# for a commitment-level keyword to count.
COMPANION_WINDOW_TOKENS = 20

# Saturation constant — Σweights = SATURATION_K maps to ~0.63 score,
# 2*K → ~0.86, 3*K → ~0.95. Tuned so 4–5 strong hits saturate near 0.9.
SATURATION_K = 25.0


@dataclass
class _CompiledKeyword:
    keyword: SignalKeyword
    pattern: re.Pattern[str]
    companion: re.Pattern[str] | None


def compile_framework(framework: SignalFramework) -> list[_CompiledKeyword]:
    """Pre-compile every keyword's regex (or escaped phrase) once."""
    compiled: list[_CompiledKeyword] = []
    for kw in framework.keywords:
        try:
            if kw.is_regex:
                pattern = re.compile(kw.phrase, re.IGNORECASE)
            else:
                # Leading word-boundary; trailing left open so plurals still
                # hit ("distribution centers" matches "distribution center").
                escaped = re.escape(kw.phrase)
                pattern = re.compile(rf"\b{escaped}", re.IGNORECASE)
        except re.error:
            # Skip malformed user-edited regex rather than crash the engine
            continue

        companion = None
        if kw.companion_pattern:
            try:
                companion = re.compile(kw.companion_pattern, re.IGNORECASE)
            except re.error:
                companion = None

        compiled.append(_CompiledKeyword(kw, pattern, companion))
    return compiled


def _companion_window(text: str, match_offset: int, match_end: int) -> str:
    """Return the slice of `text` extending COMPANION_WINDOW_TOKENS tokens
    on each side of the match."""
    # Cheap token approx — split on whitespace.
    before = text[:match_offset].split()
    after = text[match_end:].split()
    before_window = " ".join(before[-COMPANION_WINDOW_TOKENS:])
    after_window = " ".join(after[:COMPANION_WINDOW_TOKENS])
    return f"{before_window} {text[match_offset:match_end]} {after_window}"


def detect(
    chunk: TranscriptChunk,
    framework: SignalFramework,
    *,
    compiled: list[_CompiledKeyword] | None = None,
) -> list[KeywordHit]:
    """Run every keyword in `framework` against `chunk.text`.

    Returns one KeywordHit per match. If a keyword has a companion_pattern,
    the match only counts when the companion regex appears within
    COMPANION_WINDOW_TOKENS tokens of the keyword.
    """
    text = chunk.text
    if not text:
        return []

    compiled = compiled or compile_framework(framework)
    hits: list[KeywordHit] = []

    for ck in compiled:
        for m in ck.pattern.finditer(text):
            if ck.companion is not None:
                window = _companion_window(text, m.start(), m.end())
                if not ck.companion.search(window):
                    continue

            hits.append(
                KeywordHit(
                    keyword_id=ck.keyword.id,
                    chunk_id=chunk.chunk_id,
                    transcript_key=chunk.transcript_key,
                    category=ck.keyword.category,
                    phrase=ck.keyword.phrase,
                    match_text=m.group(0),
                    match_offset=m.start(),
                    weight_contribution=ck.keyword.weight,
                )
            )

    return hits


def keyword_score(hits: list[KeywordHit]) -> float:
    """Normalize a list of hits to a 0..1 score via a saturation curve.

    `1 - exp(-Σweights / K)` keeps the function monotone, bounded at 1,
    and gracefully diminishes the marginal value of additional hits.
    """
    if not hits:
        return 0.0
    total_weight = sum(h.weight_contribution for h in hits)
    return round(1.0 - math.exp(-total_weight / SATURATION_K), 4)


def commitment_evidence_bonus(hits: list[KeywordHit]) -> float:
    """0..1 bonus driven by COMMITMENT_LEVEL hits.

    These keywords already require a numeric/date companion to fire, so
    every commitment hit is high-quality evidence. We apply the same
    saturation curve but only over commitment hits.
    """
    commitment_hits = [
        h for h in hits if h.category == KeywordCategory.COMMITMENT_LEVEL
    ]
    if not commitment_hits:
        return 0.0
    return keyword_score(commitment_hits)


def hits_summary_by_category(hits: list[KeywordHit]) -> dict[str, int]:
    """Count of hits per category — for the framework breakdown chip."""
    out: dict[str, int] = {}
    for h in hits:
        out[h.category.value] = out.get(h.category.value, 0) + 1
    return out

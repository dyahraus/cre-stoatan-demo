"""Company-level score aggregation from chunk-level signal extractions."""

from __future__ import annotations

import json
from collections import Counter

from warehouse_signal.models.schemas import (
    CompanyScore,
    MoveType,
    Sector,
    TimeHorizon,
)
from warehouse_signal.storage.sqlite import Storage

# Relevance threshold — chunks below this are not considered "relevant"
RELEVANCE_THRESHOLD = 0.3

# Time horizon weights for the time bonus component
TIME_WEIGHTS: dict[str, float] = {
    "immediate": 1.0,
    "near_term": 0.8,
    "medium_term": 0.5,
    "long_term": 0.3,
    "historical": 0.1,
    "unspecified": 0.2,
}


def compute_composite_score(extractions: list[dict]) -> float:
    """Compute composite expansion score from a list of extraction dicts.

    Formula:
      40% : max expansion_score (peak signal strength)
      30% : weighted avg expansion_score (breadth, weighted by warehouse_relevance)
      15% : signal flag bonus (0.05 each for capex, build_to_suit, last_mile)
      15% : time horizon bonus (immediate/near_term weighted higher)
    """
    relevant = [e for e in extractions if e["warehouse_relevance"] >= RELEVANCE_THRESHOLD]
    if not relevant:
        return 0.0

    # Peak signal
    max_exp = max(e["expansion_score"] for e in relevant)

    # Weighted average
    total_weight = sum(e["warehouse_relevance"] for e in relevant)
    weighted_avg = (
        sum(e["expansion_score"] * e["warehouse_relevance"] for e in relevant)
        / total_weight
    )

    # Signal flag bonus
    has_capex = False
    has_bts = False
    has_lm = False
    for e in relevant:
        signals_data = json.loads(e.get("signals_json", "{}"))
        signals = signals_data.get("signals", {})
        if signals.get("capex_expansion"):
            has_capex = True
        if signals.get("build_to_suit"):
            has_bts = True
        if signals.get("last_mile_expansion"):
            has_lm = True
    flag_bonus = 0.05 * sum([has_capex, has_bts, has_lm])

    # Time horizon bonus
    time_scores = [TIME_WEIGHTS.get(e["time_horizon"], 0.2) for e in relevant]
    time_bonus = sum(time_scores) / len(time_scores)

    composite = 0.40 * max_exp + 0.30 * weighted_avg + 0.15 * flag_bonus + 0.15 * time_bonus
    return min(round(composite, 3), 1.0)


def score_company(storage: Storage, ticker: str) -> CompanyScore | None:
    """Aggregate all signal extractions for a ticker into a CompanyScore."""
    extractions = storage.get_extractions_for_ticker(ticker)
    if not extractions:
        return None

    company_name = storage.get_company_name(ticker)

    # Get sector from companies table
    try:
        company_row = storage.db["companies"].get(ticker)
        sector = Sector(company_row["sector"])
    except Exception:
        sector = Sector.OTHER

    relevant = [e for e in extractions if e["warehouse_relevance"] >= RELEVANCE_THRESHOLD]
    composite = compute_composite_score(extractions)

    # Averages
    avg_relevance = (
        sum(e["warehouse_relevance"] for e in relevant) / len(relevant)
        if relevant else 0.0
    )
    avg_expansion = (
        sum(e["expansion_score"] for e in relevant) / len(relevant)
        if relevant else 0.0
    )
    max_expansion = max((e["expansion_score"] for e in relevant), default=0.0)

    # Geographic aggregation
    geo_counter: Counter[str] = Counter()
    for e in relevant:
        geo_mentions = json.loads(e.get("geographic_mentions", "[]"))
        for g in geo_mentions:
            if isinstance(g, dict):
                geo_counter[g["region"]] += 1
    top_geos = [region for region, _ in geo_counter.most_common(5)]

    # Dominant time horizon and move type (mode among relevant chunks)
    time_counter: Counter[str] = Counter(e["time_horizon"] for e in relevant)
    move_counter: Counter[str] = Counter(e["move_type"] for e in relevant)

    dominant_th = TimeHorizon(time_counter.most_common(1)[0][0]) if time_counter else TimeHorizon.UNSPECIFIED
    dominant_mt = MoveType(move_counter.most_common(1)[0][0]) if move_counter else MoveType.UNKNOWN

    # Signal flags
    has_capex = False
    has_bts = False
    has_lm = False
    for e in relevant:
        signals_data = json.loads(e.get("signals_json", "{}"))
        signals = signals_data.get("signals", {})
        if signals.get("capex_expansion"):
            has_capex = True
        if signals.get("build_to_suit"):
            has_bts = True
        if signals.get("last_mile_expansion"):
            has_lm = True

    # Evidence snippets (top 3 by expansion_score)
    sorted_relevant = sorted(relevant, key=lambda e: e["expansion_score"], reverse=True)
    evidence = []
    for e in sorted_relevant[:3]:
        full = json.loads(e.get("raw_llm_output", "{}"))
        quote = full.get("evidence_quote", "")
        if quote:
            evidence.append(quote)

    # Transcript keys
    transcript_keys = list({e["transcript_key"] for e in extractions})

    return CompanyScore(
        ticker=ticker,
        company_name=company_name,
        sector=sector,
        composite_score=composite,
        avg_warehouse_relevance=round(avg_relevance, 3),
        avg_expansion_score=round(avg_expansion, 3),
        max_expansion_score=round(max_expansion, 3),
        num_relevant_chunks=len(relevant),
        total_chunks=len(extractions),
        top_geographies=top_geos,
        dominant_time_horizon=dominant_th,
        dominant_move_type=dominant_mt,
        has_capex_signal=has_capex,
        has_build_to_suit=has_bts,
        has_last_mile=has_lm,
        evidence_snippets=evidence,
        transcript_keys=transcript_keys,
    )


def score_all_companies(storage: Storage) -> list[CompanyScore]:
    """Score all companies that have extractions. Returns sorted descending."""
    tickers = storage.get_tickers_with_extractions()
    scores = []
    for ticker in tickers:
        score = score_company(storage, ticker)
        if score and score.composite_score > 0:
            storage.save_company_score(score)
            scores.append(score)
    return sorted(scores, key=lambda s: s.composite_score, reverse=True)

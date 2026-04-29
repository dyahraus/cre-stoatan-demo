"""API routes for the Warehouse Signal frontend."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query

from warehouse_signal.api.deps import get_storage
from warehouse_signal.models.schemas import (
    CompanyScore,
    MoveType,
    Sector,
    SignalTier,
    TimeHorizon,
)
from warehouse_signal.radar.alerts import RadarFilter, filter_scores
from warehouse_signal.scoring.aggregator import score_company, score_transcript
from warehouse_signal.scoring.tiers import (
    TIER_BOUNDS,
    TIER_DESCRIPTION,
)

router = APIRouter()


@router.get("/stats")
def api_stats() -> dict:
    """Database statistics."""
    return get_storage().get_stats()


@router.get("/scores")
def api_scores(
    min_score: float = Query(0.0, ge=0.0, le=1.0),
    sector: str | None = Query(None),
    geography: str | None = Query(None),
    move_type: str | None = Query(None),
    time_horizon: str | None = Query(None),
    top_n: int = Query(50, ge=1, le=500),
) -> list[dict]:
    """All company scores with optional filtering."""
    storage = get_storage()
    raw = storage.get_all_company_scores()
    if not raw:
        return []

    scores = [storage.row_to_company_score(row) for row in raw]

    # Build filter
    radar_filter = RadarFilter(min_score=min_score, top_n=top_n)
    if sector:
        try:
            radar_filter.sectors = [Sector(sector)]
        except ValueError:
            raise HTTPException(400, f"Unknown sector: {sector}")
    if geography:
        radar_filter.geographies = [geography]
    if move_type:
        try:
            radar_filter.move_types = [MoveType(move_type)]
        except ValueError:
            raise HTTPException(400, f"Unknown move_type: {move_type}")
    if time_horizon:
        try:
            radar_filter.time_horizons = [TimeHorizon(time_horizon)]
        except ValueError:
            raise HTTPException(400, f"Unknown time_horizon: {time_horizon}")

    filtered = filter_scores(scores, radar_filter)
    return [s.model_dump(mode="json") for s in filtered]


@router.get("/scores/{ticker}")
def api_score_detail(ticker: str) -> dict:
    """Single company score (computed fresh from extractions)."""
    storage = get_storage()
    result = score_company(storage, ticker.upper())
    if not result:
        raise HTTPException(404, f"No extractions found for {ticker}")
    return result.model_dump(mode="json")


@router.get("/scores/{ticker}/extractions")
def api_extractions(ticker: str) -> list[dict]:
    """Per-chunk signal extractions for a company."""
    storage = get_storage()
    rows = storage.get_extractions_for_ticker(ticker.upper())
    # Parse JSON string fields for the frontend
    results = []
    for row in rows:
        parsed = dict(row)
        parsed["geographic_mentions"] = json.loads(parsed.get("geographic_mentions", "[]"))
        parsed["signals_json"] = json.loads(parsed.get("signals_json", "{}"))
        # Parse raw_llm_output for evidence_quote and reasoning
        try:
            llm = json.loads(parsed.get("raw_llm_output", "{}"))
            parsed["evidence_quote"] = llm.get("evidence_quote", "")
            parsed["reasoning"] = llm.get("reasoning", "")
        except (json.JSONDecodeError, TypeError):
            parsed["evidence_quote"] = ""
            parsed["reasoning"] = ""
        results.append(parsed)
    return results


@router.get("/geographies")
def api_geographies() -> list[dict]:
    """Geography summary aggregated across all scored companies."""
    storage = get_storage()
    raw = storage.get_all_company_scores()
    if not raw:
        return []

    scores = [storage.row_to_company_score(row) for row in raw]

    geo_data: dict[str, list[float]] = {}
    geo_companies: dict[str, set[str]] = {}

    for s in scores:
        for geo in s.top_geographies:
            geo_data.setdefault(geo, []).append(s.composite_score)
            geo_companies.setdefault(geo, set()).add(s.ticker)

    results = []
    for region in sorted(
        geo_data.keys(),
        key=lambda g: sum(geo_data[g]) / len(geo_data[g]),
        reverse=True,
    ):
        score_list = geo_data[region]
        results.append({
            "region": region,
            "num_companies": len(geo_companies[region]),
            "avg_score": round(sum(score_list) / len(score_list), 3),
            "max_score": round(max(score_list), 3),
            "tickers": sorted(geo_companies[region]),
        })

    return results


@router.get("/enums")
def api_enums() -> dict:
    """Available enum values for filter dropdowns."""
    return {
        "sectors": [s.value for s in Sector],
        "move_types": [m.value for m in MoveType],
        "time_horizons": [t.value for t in TimeHorizon],
        "tiers": [t.value for t in SignalTier],
        "tier_bounds": [
            {"tier": t.value, "min_score": bound, "description": TIER_DESCRIPTION[t]}
            for t, bound in TIER_BOUNDS
        ],
    }


# ---------------------------------------------------------------------------
# Per-transcript score + history (Phase 1C / 1D)
# ---------------------------------------------------------------------------

@router.get("/transcripts/{quarter_key}/score")
def api_transcript_score(quarter_key: str) -> dict:
    """Return the persisted TranscriptScore — fall back to a fresh compute
    if none has been saved yet."""
    storage = get_storage()
    score = storage.get_transcript_score(quarter_key)
    if score is None:
        score = score_transcript(storage, quarter_key)
        if score is None:
            raise HTTPException(404, f"No score for {quarter_key}")
    return score.model_dump(mode="json")


@router.get("/companies/{ticker}/history")
def api_company_history(ticker: str) -> list[dict]:
    """Chronological list of TranscriptScore rows for a ticker."""
    storage = get_storage()
    scores = storage.get_transcript_scores_for_ticker(ticker.upper())
    return [
        {
            "quarter_key": s.quarter_key,
            "year": s.year,
            "quarter": s.quarter,
            "framework_id": s.framework_id,
            "composite_score": s.composite_score,
            "tier": s.tier.value,
            "confidence": s.confidence,
            "scored_at": s.scored_at.isoformat(),
            "extracted_metrics": s.extracted_metrics.model_dump(),
            "top_evidence": (
                s.top_contributions[0].evidence_quote
                if s.top_contributions
                else ""
            ),
        }
        for s in scores
    ]


@router.get("/companies")
def api_companies(q: str | None = Query(None)) -> list[dict]:
    """Lookup helper for the scan page's ticker validation chips.
    Returns ticker + name (and sector) for known companies."""
    storage = get_storage()
    rows = list(storage.db["companies"].rows_where("active = 1"))
    if q:
        ql = q.upper()
        rows = [r for r in rows if ql in r["ticker"].upper()]
    return [
        {"ticker": r["ticker"], "name": r["name"], "sector": r["sector"]}
        for r in rows
    ]

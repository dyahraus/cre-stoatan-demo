"""Score aggregation: hybrid (LLM + keyword) chunk scoring rolled up into
per-transcript and per-company composites.

Hybrid chunk score:
    chunk_score = 0.55 * llm_expansion
                + 0.30 * keyword_score
                + 0.15 * commitment_evidence_bonus

Transcript composite (over relevant chunks):
    composite = 0.40 * max_chunk_score
              + 0.30 * weighted_avg_chunk_score   (weighted by warehouse_relevance)
              + 0.15 * flag_bonus                 (capex / build-to-suit / last-mile)
              + 0.15 * time_bonus                 (immediate/near-term weighted higher)

A chunk counts as "relevant" when either the LLM relevance crosses the
threshold OR the chunk has at least one keyword hit. This stops a
keyword-rich chunk with low LLM relevance from being silently dropped.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone

from warehouse_signal.analysis.concept_engine import concept_score
from warehouse_signal.analysis.keyword_engine import (
    commitment_evidence_bonus,
    hits_summary_by_category,
    keyword_score,
)
from warehouse_signal.models.schemas import (
    BoostConfig,
    ChunkContribution,
    CompanyScore,
    ConceptHit,
    ConceptMode,
    ExtractedMetrics,
    KeywordCategory,
    KeywordHit,
    MoveType,
    ScoreComponents,
    SectionType,
    Sector,
    SignalFramework,
    SignalTier,
    TimeHorizon,
    TranscriptScore,
)
from warehouse_signal.scoring.tiers import tier_for_score
from warehouse_signal.storage.sqlite import Storage

# A chunk counts as relevant when its LLM warehouse_relevance is at or
# above this threshold. Keyword-rich chunks override this bar.
RELEVANCE_THRESHOLD = 0.3

# Hybrid chunk-score weights (must sum to 1.0).
# Concepts slot in alongside keywords once the engine has any concepts +
# a configured embedder; otherwise the concept term is 0 and the math
# still hits 1.0 from the other three.
W_LLM = 0.40
W_KEYWORD = 0.25
W_CONCEPT = 0.20
W_COMMITMENT = 0.15

# Transcript-level composite weights (must sum to 1.0).
W_MAX = 0.40
W_AVG = 0.30
W_FLAG = 0.15
W_TIME = 0.15

# Time horizon weights for the time bonus component
TIME_WEIGHTS: dict[str, float] = {
    "immediate": 1.0,
    "near_term": 0.8,
    "medium_term": 0.5,
    "long_term": 0.3,
    "historical": 0.1,
    "unspecified": 0.2,
}


# ---------------------------------------------------------------------------
# Hybrid chunk scoring
# ---------------------------------------------------------------------------

def compute_chunk_score(
    llm_expansion: float,
    kw_hits: list[KeywordHit],
    concept_hits: list[ConceptHit] | None = None,
) -> tuple[float, float, float, float]:
    """Hybrid chunk score across LLM + keyword + concept + commitment.

    Returns (hybrid_score, kw_part, commit_part, concept_part).
    """
    kw_part = keyword_score(kw_hits)
    commit_part = commitment_evidence_bonus(kw_hits)
    concept_part = concept_score(concept_hits or [])
    hybrid = (
        W_LLM * llm_expansion
        + W_KEYWORD * kw_part
        + W_CONCEPT * concept_part
        + W_COMMITMENT * commit_part
    )
    return round(hybrid, 4), kw_part, commit_part, concept_part


# ---------------------------------------------------------------------------
# Boost application
# ---------------------------------------------------------------------------

def _section_boost(boosts: BoostConfig, section_type: str) -> float:
    if section_type == "prepared_remarks":
        return boosts.prepared_remarks
    if section_type == "qa":
        return boosts.qa
    return boosts.full


def _speaker_boost(boosts: BoostConfig, speaker_role: str | None) -> float:
    """Case-insensitive prefix match: "CEO" hits 'Chief Executive Officer'."""
    if not speaker_role or not boosts.speaker_role:
        return 1.0
    sr = speaker_role.strip().lower()
    for key, mult in boosts.speaker_role.items():
        if not key:
            continue
        kl = key.strip().lower()
        if not kl:
            continue
        if sr.startswith(kl) or kl in sr:
            return mult
    return 1.0


def apply_boosts(
    base_score: float,
    section_type: str,
    speaker_role: str | None,
    boosts: BoostConfig,
) -> tuple[float, float]:
    """Apply section + speaker multipliers to a 0..1 score.

    Returns (boosted_score_clamped, applied_multiplier). The applied
    multiplier is exposed in ScoreComponents so the breakdown panel can
    show "1.32× from CEO + prepared remarks → clamped to 1.0".
    """
    mult = _section_boost(boosts, section_type) * _speaker_boost(
        boosts, speaker_role
    )
    boosted = base_score * mult
    return min(max(boosted, 0.0), 1.0), round(mult, 4)


# ---------------------------------------------------------------------------
# Transcript-level scoring
# ---------------------------------------------------------------------------

def score_transcript(
    storage: Storage,
    quarter_key: str,
    framework: SignalFramework | None = None,
) -> TranscriptScore | None:
    """Compute a per-transcript score from extractions + keyword hits.

    Returns None when the transcript has no chunks at all.
    """
    framework = framework or storage.get_default_framework()
    if framework is None:
        # Should never happen — _seed_default_framework_if_empty guarantees one.
        raise RuntimeError("No signal framework available; DB seed is missing.")

    chunks = storage.get_chunks_for_transcript(quarter_key)
    if not chunks:
        return None

    extractions = {
        e["chunk_id"]: e
        for e in storage.get_extractions_for_transcript(quarter_key)
    }
    hits_by_chunk: dict[str, list[KeywordHit]] = {}
    for hit_row in storage.get_hits_for_transcript(quarter_key):
        try:
            kh = KeywordHit(
                keyword_id=hit_row["keyword_id"],
                chunk_id=hit_row["chunk_id"],
                transcript_key=hit_row["transcript_key"],
                category=KeywordCategory(hit_row["category"]),
                phrase=hit_row["phrase"],
                match_text=hit_row["match_text"],
                match_offset=hit_row["match_offset"],
                weight_contribution=hit_row["weight_contribution"],
            )
        except (ValueError, KeyError):
            continue
        hits_by_chunk.setdefault(kh.chunk_id, []).append(kh)

    # Concept hits — keyed per (chunk, framework) so re-running with a
    # different framework doesn't pollute another framework's history.
    concepts_by_chunk: dict[str, list[ConceptHit]] = {}
    for ch_row in storage.get_concept_hits_for_transcript(
        quarter_key, framework.id
    ):
        try:
            ch = ConceptHit(
                concept_id=ch_row["concept_id"],
                chunk_id=ch_row["chunk_id"],
                transcript_key=ch_row["transcript_key"],
                category=KeywordCategory(ch_row["category"]),
                label=ch_row["label"],
                similarity=ch_row["similarity"],
                weight_contribution=ch_row["weight_contribution"],
                mode_used=ConceptMode(ch_row["mode_used"]),
            )
        except (ValueError, KeyError):
            continue
        concepts_by_chunk.setdefault(ch.chunk_id, []).append(ch)

    # Pull ticker/year/quarter from the transcript row
    transcript_row = storage.db["transcripts"].get(quarter_key)
    ticker = transcript_row["ticker"]
    year = transcript_row["year"]
    quarter = transcript_row["quarter"]

    relevant_chunks: list[dict] = []
    chunk_scores: list[float] = []
    contributions: list[ChunkContribution] = []
    flag_capex = False
    flag_bts = False
    flag_lm = False

    capex_total = 0
    sqft_total = 0
    facility_total = 0
    completion_dates: list[str] = []

    time_horizons: list[str] = []
    move_types: list[str] = []

    all_hits: list[KeywordHit] = []
    all_concept_hits: list[ConceptHit] = []
    boost_multipliers: list[float] = []
    for chunk in chunks:
        cid = chunk["chunk_id"]
        ext = extractions.get(cid)
        kw_hits = hits_by_chunk.get(cid, [])
        c_hits = concepts_by_chunk.get(cid, [])
        all_hits.extend(kw_hits)
        all_concept_hits.extend(c_hits)

        llm_relevance = ext["warehouse_relevance"] if ext else 0.0
        llm_expansion = ext["expansion_score"] if ext else 0.0

        base_score, kw_part, commit_part, concept_part = compute_chunk_score(
            llm_expansion, kw_hits, c_hits
        )

        # Apply section + speaker boosts from the framework
        chunk_score_value, applied_mult = apply_boosts(
            base_score,
            chunk["section_type"],
            chunk.get("speaker_role"),
            framework.boosts,
        )

        is_relevant = (
            llm_relevance >= RELEVANCE_THRESHOLD
            or len(kw_hits) > 0
            or len(c_hits) > 0
        )
        if not is_relevant:
            continue
        boost_multipliers.append(applied_mult)

        relevant_chunks.append(
            {
                **(ext or {}),
                "chunk_id": cid,
                "warehouse_relevance": max(
                    llm_relevance,
                    kw_part,
                    concept_part,  # concept strength can also pull a chunk in
                ),
                "expansion_score": chunk_score_value,
                "_kw_part": kw_part,
                "_commit_part": commit_part,
                "_concept_part": concept_part,
                "_kw_count": len(kw_hits),
                "_concept_count": len(c_hits),
            }
        )
        chunk_scores.append(chunk_score_value)

        # Pull signal flags + extracted metrics from the LLM payload, if present.
        if ext:
            try:
                signals_data = json.loads(ext.get("signals_json", "{}"))
                signals = signals_data.get("signals", {})
                if signals.get("capex_expansion"):
                    flag_capex = True
                if signals.get("build_to_suit"):
                    flag_bts = True
                if signals.get("last_mile_expansion"):
                    flag_lm = True
                if signals.get("capex_amount_usd"):
                    capex_total += int(signals["capex_amount_usd"])
                if signals.get("square_footage_sqft"):
                    sqft_total += int(signals["square_footage_sqft"])
                if signals.get("facility_count"):
                    facility_total += int(signals["facility_count"])
                if signals.get("target_completion"):
                    completion_dates.append(str(signals["target_completion"]))
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
            time_horizons.append(ext.get("time_horizon") or "unspecified")
            move_types.append(ext.get("move_type") or "unknown")

        # Build contribution record (we'll keep the top 5 below).
        evidence_quote = ""
        reasoning = ""
        if ext:
            try:
                payload = json.loads(ext.get("raw_llm_output") or "{}")
                evidence_quote = payload.get("evidence_quote", "")
                reasoning = payload.get("reasoning", "")
            except (json.JSONDecodeError, TypeError):
                pass

        contributions.append(
            ChunkContribution(
                chunk_id=cid,
                chunk_index=chunk["chunk_index"],
                section_type=SectionType(chunk["section_type"]),
                contribution=chunk_score_value,
                expansion_score=llm_expansion,
                warehouse_relevance=llm_relevance,
                keyword_hit_count=len(kw_hits),
                evidence_quote=evidence_quote,
                reasoning=reasoning,
            )
        )

    if not relevant_chunks:
        # Nothing relevant — return a Noise-tier zero score for traceability.
        return TranscriptScore(
            quarter_key=quarter_key,
            ticker=ticker,
            year=year,
            quarter=quarter,
            framework_id=framework.id,
            composite_score=0.0,
            tier=SignalTier.NOISE,
            confidence=0.0,
            score_components=ScoreComponents(),
            top_contributions=[],
            keyword_hit_summary=hits_summary_by_category(all_hits),
            extracted_metrics=ExtractedMetrics(),
            num_relevant_chunks=0,
            total_chunks=len(chunks),
        )

    # Component math
    max_chunk = max(chunk_scores)
    total_weight = sum(c["warehouse_relevance"] for c in relevant_chunks) or 1.0
    weighted_avg = (
        sum(c["expansion_score"] * c["warehouse_relevance"] for c in relevant_chunks)
        / total_weight
    )
    flag_bonus = sum([flag_capex, flag_bts, flag_lm]) / 3.0
    time_bonus = (
        sum(TIME_WEIGHTS.get(th, 0.2) for th in time_horizons)
        / len(time_horizons)
        if time_horizons
        else 0.2
    )

    composite = (
        W_MAX * max_chunk
        + W_AVG * weighted_avg
        + W_FLAG * flag_bonus
        + W_TIME * time_bonus
    )
    composite = round(min(composite, 1.0), 4)

    # Confidence — supporting chunks normalized
    confidence = round(min(len(relevant_chunks) / 5.0, 1.0), 3)

    # Framework-side rollups (transparency)
    keyword_component = round(
        sum(c["_kw_part"] for c in relevant_chunks) / len(relevant_chunks), 4
    )
    commitment_component = round(
        sum(c["_commit_part"] for c in relevant_chunks) / len(relevant_chunks), 4
    )
    concept_component = round(
        sum(c["_concept_part"] for c in relevant_chunks) / len(relevant_chunks),
        4,
    )

    avg_boost = (
        round(sum(boost_multipliers) / len(boost_multipliers), 4)
        if boost_multipliers
        else 1.0
    )

    components = ScoreComponents(
        max_expansion=round(max_chunk, 4),
        weighted_avg=round(weighted_avg, 4),
        flag_bonus=round(flag_bonus, 4),
        time_bonus=round(time_bonus, 4),
        keyword_component=keyword_component,
        commitment_component=commitment_component,
        concept_component=concept_component,
        boost_multiplier=avg_boost,
    )

    contributions.sort(key=lambda c: c.contribution, reverse=True)
    top_contributions = contributions[:5]

    extracted_metrics = ExtractedMetrics(
        capex_amount_usd=capex_total or None,
        square_footage_sqft=sqft_total or None,
        facility_count=facility_total or None,
        target_completion=min(completion_dates) if completion_dates else None,
    )

    return TranscriptScore(
        quarter_key=quarter_key,
        ticker=ticker,
        year=year,
        quarter=quarter,
        framework_id=framework.id,
        composite_score=composite,
        tier=tier_for_score(composite),
        confidence=confidence,
        score_components=components,
        top_contributions=top_contributions,
        keyword_hit_summary=hits_summary_by_category(all_hits),
        extracted_metrics=extracted_metrics,
        num_relevant_chunks=len(relevant_chunks),
        total_chunks=len(chunks),
        scored_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Backward-compatible chunk-level composite (used by demo /score endpoint)
# ---------------------------------------------------------------------------

def compute_composite_score(extractions: list[dict]) -> float:
    """Legacy function — composite from raw LLM extractions only.

    Kept for the existing /api/demo/score endpoint which doesn't have
    keyword hits handy. New code should prefer score_transcript.
    """
    relevant = [
        e for e in extractions if e["warehouse_relevance"] >= RELEVANCE_THRESHOLD
    ]
    if not relevant:
        return 0.0

    max_exp = max(e["expansion_score"] for e in relevant)
    total_weight = sum(e["warehouse_relevance"] for e in relevant)
    weighted_avg = (
        sum(e["expansion_score"] * e["warehouse_relevance"] for e in relevant)
        / total_weight
    )

    has_capex = False
    has_bts = False
    has_lm = False
    for e in relevant:
        try:
            signals_data = json.loads(e.get("signals_json", "{}"))
            signals = signals_data.get("signals", {})
        except (json.JSONDecodeError, TypeError):
            continue
        if signals.get("capex_expansion"):
            has_capex = True
        if signals.get("build_to_suit"):
            has_bts = True
        if signals.get("last_mile_expansion"):
            has_lm = True
    flag_bonus = sum([has_capex, has_bts, has_lm]) / 3.0

    time_scores = [TIME_WEIGHTS.get(e["time_horizon"], 0.2) for e in relevant]
    time_bonus = sum(time_scores) / len(time_scores)

    composite = (
        W_MAX * max_exp + W_AVG * weighted_avg + W_FLAG * flag_bonus + W_TIME * time_bonus
    )
    return min(round(composite, 3), 1.0)


# ---------------------------------------------------------------------------
# Company-level scoring (aggregates across transcript_scores)
# ---------------------------------------------------------------------------

def score_company(storage: Storage, ticker: str) -> CompanyScore | None:
    """Aggregate the ticker's per-transcript scores into a CompanyScore.

    Falls back to legacy chunk-extraction aggregation when the ticker has
    no TranscriptScore rows yet (so existing /api/scores/{ticker} keeps
    working through Phase 1 transition).
    """
    transcript_scores = storage.get_transcript_scores_for_ticker(ticker)
    if transcript_scores:
        return _company_from_transcript_scores(storage, ticker, transcript_scores)

    # Legacy fallback path.
    return _company_from_extractions(storage, ticker)


def _company_from_transcript_scores(
    storage: Storage, ticker: str, scores: list[TranscriptScore]
) -> CompanyScore:
    """Most-recent-wins aggregation: the latest TranscriptScore drives
    the company composite, and prior quarters are folded in via
    transcript_keys for the history view."""
    company_name = storage.get_company_name(ticker)
    sector = _lookup_sector(storage, ticker)

    latest = max(scores, key=lambda s: (s.year, s.quarter))

    # Average across all transcripts for relevance / expansion stats
    avg_relevance = (
        sum(_avg_chunk_relevance(s) for s in scores) / len(scores)
        if scores
        else 0.0
    )
    avg_expansion = (
        sum(s.composite_score for s in scores) / len(scores) if scores else 0.0
    )
    max_expansion = max((s.composite_score for s in scores), default=0.0)

    # Flag union across all transcripts
    has_capex = any(
        s.extracted_metrics.capex_amount_usd is not None for s in scores
    )
    has_bts = any(
        any("build_to_suit" in c.evidence_quote.lower() for c in s.top_contributions)
        for s in scores
    )
    has_lm = any(
        any("last-mile" in c.evidence_quote.lower() or "last mile" in c.evidence_quote.lower() for c in s.top_contributions)
        for s in scores
    )

    # Geography aggregation pulled from extractions table directly
    top_geos = _top_geographies(storage, ticker)

    # Dominant time horizon / move type from latest transcript chunks
    time_counter: Counter[str] = Counter()
    move_counter: Counter[str] = Counter()
    for ext in storage.get_extractions_for_transcript(latest.quarter_key):
        time_counter[ext.get("time_horizon") or "unspecified"] += 1
        move_counter[ext.get("move_type") or "unknown"] += 1

    dominant_th = (
        TimeHorizon(time_counter.most_common(1)[0][0])
        if time_counter
        else TimeHorizon.UNSPECIFIED
    )
    dominant_mt = (
        MoveType(move_counter.most_common(1)[0][0])
        if move_counter
        else MoveType.UNKNOWN
    )

    return CompanyScore(
        ticker=ticker,
        company_name=company_name,
        sector=sector,
        composite_score=latest.composite_score,
        tier=latest.tier,
        confidence=latest.confidence,
        avg_warehouse_relevance=round(avg_relevance, 3),
        avg_expansion_score=round(avg_expansion, 3),
        max_expansion_score=round(max_expansion, 3),
        num_relevant_chunks=latest.num_relevant_chunks,
        total_chunks=latest.total_chunks,
        top_geographies=top_geos,
        dominant_time_horizon=dominant_th,
        dominant_move_type=dominant_mt,
        has_capex_signal=has_capex,
        has_build_to_suit=has_bts,
        has_last_mile=has_lm,
        evidence_snippets=[c.evidence_quote for c in latest.top_contributions if c.evidence_quote][:3],
        transcript_keys=[s.quarter_key for s in scores],
        score_components=latest.score_components,
        top_contributions=latest.top_contributions,
        scored_at=datetime.now(timezone.utc),
    )


def _company_from_extractions(
    storage: Storage, ticker: str
) -> CompanyScore | None:
    """Legacy aggregator — used when no TranscriptScore rows exist yet."""
    extractions = storage.get_extractions_for_ticker(ticker)
    if not extractions:
        return None

    company_name = storage.get_company_name(ticker)
    sector = _lookup_sector(storage, ticker)

    relevant = [
        e for e in extractions if e["warehouse_relevance"] >= RELEVANCE_THRESHOLD
    ]
    composite = compute_composite_score(extractions)

    avg_relevance = (
        sum(e["warehouse_relevance"] for e in relevant) / len(relevant)
        if relevant
        else 0.0
    )
    avg_expansion = (
        sum(e["expansion_score"] for e in relevant) / len(relevant)
        if relevant
        else 0.0
    )
    max_expansion = max((e["expansion_score"] for e in relevant), default=0.0)

    geo_counter: Counter[str] = Counter()
    for e in relevant:
        for g in json.loads(e.get("geographic_mentions", "[]")):
            if isinstance(g, dict):
                geo_counter[g["region"]] += 1
    top_geos = [region for region, _ in geo_counter.most_common(5)]

    time_counter: Counter[str] = Counter(e["time_horizon"] for e in relevant)
    move_counter: Counter[str] = Counter(e["move_type"] for e in relevant)
    dominant_th = (
        TimeHorizon(time_counter.most_common(1)[0][0])
        if time_counter
        else TimeHorizon.UNSPECIFIED
    )
    dominant_mt = (
        MoveType(move_counter.most_common(1)[0][0])
        if move_counter
        else MoveType.UNKNOWN
    )

    has_capex = False
    has_bts = False
    has_lm = False
    for e in relevant:
        try:
            signals_data = json.loads(e.get("signals_json", "{}"))
            signals = signals_data.get("signals", {})
        except (json.JSONDecodeError, TypeError):
            continue
        if signals.get("capex_expansion"):
            has_capex = True
        if signals.get("build_to_suit"):
            has_bts = True
        if signals.get("last_mile_expansion"):
            has_lm = True

    sorted_relevant = sorted(
        relevant, key=lambda e: e["expansion_score"], reverse=True
    )
    evidence: list[str] = []
    for e in sorted_relevant[:3]:
        try:
            full = json.loads(e.get("raw_llm_output", "{}"))
            quote = full.get("evidence_quote", "")
            if quote:
                evidence.append(quote)
        except (json.JSONDecodeError, TypeError):
            continue

    transcript_keys = list({e["transcript_key"] for e in extractions})

    return CompanyScore(
        ticker=ticker,
        company_name=company_name,
        sector=sector,
        composite_score=composite,
        tier=tier_for_score(composite),
        confidence=round(min(len(relevant) / 5.0, 1.0), 3),
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


def _avg_chunk_relevance(score: TranscriptScore) -> float:
    if not score.top_contributions:
        return 0.0
    return sum(c.warehouse_relevance for c in score.top_contributions) / len(
        score.top_contributions
    )


def _lookup_sector(storage: Storage, ticker: str) -> Sector:
    try:
        company_row = storage.db["companies"].get(ticker)
        return Sector(company_row["sector"])
    except Exception:
        return Sector.OTHER


def _top_geographies(storage: Storage, ticker: str, k: int = 5) -> list[str]:
    geo_counter: Counter[str] = Counter()
    for e in storage.get_extractions_for_ticker(ticker):
        try:
            for g in json.loads(e.get("geographic_mentions", "[]")):
                if isinstance(g, dict):
                    geo_counter[g["region"]] += 1
        except (json.JSONDecodeError, TypeError):
            continue
    return [region for region, _ in geo_counter.most_common(k)]


def score_all_companies(storage: Storage) -> list[CompanyScore]:
    """Score every company that has any extractions, persist, return sorted desc."""
    tickers = storage.get_tickers_with_extractions()
    out: list[CompanyScore] = []
    for ticker in tickers:
        cs = score_company(storage, ticker)
        if cs and cs.composite_score > 0:
            storage.save_company_score(cs)
            out.append(cs)
    return sorted(out, key=lambda s: s.composite_score, reverse=True)

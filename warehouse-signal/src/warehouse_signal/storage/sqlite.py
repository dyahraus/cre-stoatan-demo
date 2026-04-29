"""SQLite storage backend for the MVP.

Uses sqlite-utils for convenience. Designed to be replaceable with
PostgreSQL later without changing the rest of the codebase.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import sqlite_utils

from warehouse_signal.config import Config
from warehouse_signal.models.schemas import (
    BoostConfig,
    ChunkContribution,
    ChunkExtraction,
    Company,
    CompanyScore,
    ExtractedMetrics,
    KeywordCategory,
    KeywordHit,
    MoveType,
    ScanJob,
    ScanJobStatus,
    ScoreComponents,
    Sector,
    SignalFramework,
    SignalKeyword,
    SignalTier,
    TimeHorizon,
    Transcript,
    TranscriptChunk,
    TranscriptScore,
    Watchlist,
)


class Storage:
    """SQLite-backed storage for transcripts, companies, and chunks."""

    def __init__(self, db_path: Path | str | None = None):
        # Re-read env at construction time so test fixtures that monkeypatch
        # DATABASE_PATH after import are honored. Falls back to the Config
        # default when nothing's been set.
        import os
        if db_path is None:
            env_path = os.getenv("DATABASE_PATH")
            db_path = env_path if env_path else Config.DATABASE_PATH
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        import sqlite3
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self.db = sqlite_utils.Database(self._conn)
        self._ensure_tables()

    def close(self) -> None:
        """Release the underlying SQLite connection.

        Called by tests + lifespan teardown so files unlock immediately
        instead of waiting on Python GC.
        """
        try:
            self._conn.close()
        except Exception:
            pass

    def _ensure_tables(self) -> None:
        """Create tables if they don't exist."""

        # Companies
        if "companies" not in self.db.table_names():
            self.db["companies"].create(
                {
                    "ticker": str,
                    "name": str,
                    "sector": str,
                    "cik": str,
                    "sp500": int,
                    "geo_exposure": str,  # JSON array
                    "active": int,
                    "created_at": str,
                    "updated_at": str,
                },
                pk="ticker",
                if_not_exists=True,
            )

        # Transcripts (metadata + raw text)
        if "transcripts" not in self.db.table_names():
            self.db["transcripts"].create(
                {
                    "quarter_key": str,       # e.g. "AAPL_2024Q3"
                    "ticker": str,
                    "year": int,
                    "quarter": int,
                    "call_date": str,
                    "call_timing": str,
                    "provider": str,
                    "raw_text": str,
                    "sections_json": str,     # JSON serialized sections
                    "fetched_at": str,
                    "processed": int,         # 0 = not yet analyzed, 1 = analyzed
                },
                pk="quarter_key",
                if_not_exists=True,
            )
            self.db["transcripts"].create_index(["ticker"], if_not_exists=True)
            self.db["transcripts"].create_index(["processed"], if_not_exists=True)
            self.db["transcripts"].create_index(["year", "quarter"], if_not_exists=True)

        # Chunks
        if "chunks" not in self.db.table_names():
            self.db["chunks"].create(
                {
                    "chunk_id": str,
                    "transcript_key": str,
                    "chunk_index": int,
                    "text": str,
                    "section_type": str,
                    "speaker": str,
                    "speaker_role": str,
                    "token_estimate": int,
                },
                pk="chunk_id",
                if_not_exists=True,
            )
            self.db["chunks"].create_index(["transcript_key"], if_not_exists=True)

        # Signal extractions (populated by the analysis stage)
        if "signal_extractions" not in self.db.table_names():
            self.db["signal_extractions"].create(
                {
                    "chunk_id": str,
                    "transcript_key": str,
                    "extraction_model": str,
                    "extraction_version": str,
                    "warehouse_relevance": float,
                    "expansion_score": float,
                    "move_type": str,
                    "time_horizon": str,
                    "geographic_mentions": str,  # JSON
                    "signals_json": str,          # Full structured extraction
                    "raw_llm_output": str,
                    "extracted_at": str,
                },
                pk="chunk_id",
                if_not_exists=True,
            )
            self.db["signal_extractions"].create_index(
                ["transcript_key"], if_not_exists=True
            )

        # Company scores (aggregated from signal_extractions)
        if "company_scores" not in self.db.table_names():
            self.db["company_scores"].create(
                {
                    "ticker": str,
                    "company_name": str,
                    "sector": str,
                    "composite_score": float,
                    "tier": str,
                    "confidence": float,
                    "avg_warehouse_relevance": float,
                    "avg_expansion_score": float,
                    "max_expansion_score": float,
                    "num_relevant_chunks": int,
                    "total_chunks": int,
                    "top_geographies": str,       # JSON
                    "dominant_time_horizon": str,
                    "dominant_move_type": str,
                    "has_capex_signal": int,
                    "has_build_to_suit": int,
                    "has_last_mile": int,
                    "evidence_snippets": str,     # JSON
                    "transcript_keys": str,       # JSON
                    "score_components_json": str,
                    "top_contributions_json": str,
                    "scored_at": str,
                },
                pk="ticker",
                if_not_exists=True,
            )
            self.db["company_scores"].create_index(
                ["composite_score"], if_not_exists=True
            )

        # Signal frameworks (configurable keyword libraries)
        if "signal_frameworks" not in self.db.table_names():
            self.db["signal_frameworks"].create(
                {
                    "id": str,
                    "name": str,
                    "description": str,
                    "is_default": int,
                    "created_at": str,
                    "updated_at": str,
                },
                pk="id",
                if_not_exists=True,
            )

        if "signal_keywords" not in self.db.table_names():
            self.db["signal_keywords"].create(
                {
                    "id": str,
                    "framework_id": str,
                    "category": str,
                    "phrase": str,
                    "is_regex": int,
                    "weight": float,
                    "companion_pattern": str,
                    "notes": str,
                    "created_at": str,
                },
                pk="id",
                if_not_exists=True,
            )
            self.db["signal_keywords"].create_index(
                ["framework_id"], if_not_exists=True
            )

        if "keyword_hits" not in self.db.table_names():
            self.db["keyword_hits"].create(
                {
                    "id": str,
                    "keyword_id": str,
                    "chunk_id": str,
                    "transcript_key": str,
                    "framework_id": str,
                    "category": str,
                    "phrase": str,
                    "match_text": str,
                    "match_offset": int,
                    "weight_contribution": float,
                    "created_at": str,
                },
                pk="id",
                if_not_exists=True,
            )
            self.db["keyword_hits"].create_index(["chunk_id"], if_not_exists=True)
            self.db["keyword_hits"].create_index(
                ["transcript_key"], if_not_exists=True
            )

        # Per-transcript scores
        if "transcript_scores" not in self.db.table_names():
            self.db["transcript_scores"].create(
                {
                    "quarter_key": str,
                    "ticker": str,
                    "year": int,
                    "quarter": int,
                    "framework_id": str,
                    "composite_score": float,
                    "tier": str,
                    "confidence": float,
                    "score_components_json": str,
                    "top_contributions_json": str,
                    "keyword_hit_summary_json": str,
                    "extracted_metrics_json": str,
                    "num_relevant_chunks": int,
                    "total_chunks": int,
                    "scored_at": str,
                },
                pk="quarter_key",
                if_not_exists=True,
            )
            self.db["transcript_scores"].create_index(
                ["ticker", "year", "quarter"], if_not_exists=True
            )

        # Watchlists (Phase 3)
        if "watchlists" not in self.db.table_names():
            self.db["watchlists"].create(
                {
                    "id": str,
                    "name": str,
                    "tickers_json": str,
                    "created_at": str,
                    "updated_at": str,
                },
                pk="id",
                if_not_exists=True,
            )

        # Scan jobs (Phase 3)
        if "scan_jobs" not in self.db.table_names():
            self.db["scan_jobs"].create(
                {
                    "id": str,
                    "status": str,
                    "params_json": str,
                    "progress_json": str,
                    "results_summary_json": str,
                    "started_at": str,
                    "finished_at": str,
                    "error": str,
                    "created_at": str,
                },
                pk="id",
                if_not_exists=True,
            )

        # Seed a default signal framework if none exists yet
        self._seed_default_framework_if_empty()

    # ------------------------------------------------------------------
    # Companies
    # ------------------------------------------------------------------

    def upsert_company(self, company: Company) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.db["companies"].upsert(
            {
                "ticker": company.ticker,
                "name": company.name,
                "sector": company.sector.value,
                "cik": company.cik or "",
                "sp500": int(company.sp500),
                "geo_exposure": json.dumps(company.geo_exposure),
                "active": int(company.active),
                "updated_at": now,
            },
            pk="ticker",
            alter=True,
        )

    def upsert_companies(self, companies: list[Company]) -> int:
        for c in companies:
            self.upsert_company(c)
        return len(companies)

    def get_active_tickers(self) -> list[str]:
        return [
            row["ticker"]
            for row in self.db["companies"].rows_where("active = 1")
        ]

    # ------------------------------------------------------------------
    # Transcripts
    # ------------------------------------------------------------------

    def has_transcript(self, ticker: str, year: int, quarter: int) -> bool:
        key = f"{ticker}_{year}Q{quarter}"
        try:
            self.db["transcripts"].get(key)
            return True
        except sqlite_utils.db.NotFoundError:
            return False

    def save_transcript(self, transcript: Transcript) -> None:
        sections_data = [
            {
                "section_type": s.section_type.value,
                "speaker": s.speaker,
                "speaker_role": s.speaker_role,
                "text": s.text,
            }
            for s in transcript.sections
        ]

        self.db["transcripts"].upsert(
            {
                "quarter_key": transcript.quarter_key,
                "ticker": transcript.metadata.ticker,
                "year": transcript.metadata.year,
                "quarter": transcript.metadata.quarter,
                "call_date": transcript.metadata.call_date.isoformat() if transcript.metadata.call_date else None,
                "call_timing": transcript.metadata.call_timing.value,
                "provider": transcript.metadata.provider,
                "raw_text": transcript.raw_text,
                "sections_json": json.dumps(sections_data),
                "fetched_at": transcript.fetched_at.isoformat(),
                "processed": 0,
            },
            pk="quarter_key",
            alter=True,
        )

    def save_chunks(self, chunks: list[TranscriptChunk]) -> None:
        for chunk in chunks:
            self.db["chunks"].upsert(
                {
                    "chunk_id": chunk.chunk_id,
                    "transcript_key": chunk.transcript_key,
                    "chunk_index": chunk.chunk_index,
                    "text": chunk.text,
                    "section_type": chunk.section_type.value,
                    "speaker": chunk.speaker,
                    "speaker_role": chunk.speaker_role,
                    "token_estimate": chunk.token_estimate,
                },
                pk="chunk_id",
            )

    def get_unprocessed_transcripts(self, limit: int = 50) -> list[dict]:
        """Get transcript keys that haven't been analyzed yet."""
        return list(
            self.db["transcripts"].rows_where(
                "processed = 0",
                limit=limit,
            )
        )

    def mark_processed(self, quarter_key: str) -> None:
        self.db["transcripts"].update(quarter_key, {"processed": 1})

    # ------------------------------------------------------------------
    # Chunks (query)
    # ------------------------------------------------------------------

    def get_chunks_for_transcript(self, quarter_key: str) -> list[dict]:
        """Get all chunks for a transcript, ordered by chunk_index."""
        return list(
            self.db["chunks"].rows_where(
                "transcript_key = ?", [quarter_key], order_by="chunk_index"
            )
        )

    def get_company_name(self, ticker: str) -> str:
        """Get company name by ticker, falling back to ticker itself."""
        try:
            row = self.db["companies"].get(ticker)
            return row["name"]
        except sqlite_utils.db.NotFoundError:
            return ticker

    # ------------------------------------------------------------------
    # Signal Extractions
    # ------------------------------------------------------------------

    def save_extraction(
        self,
        chunk_id: str,
        transcript_key: str,
        model: str,
        version: str,
        extraction: ChunkExtraction,
    ) -> None:
        """Save a chunk-level signal extraction."""
        self.db["signal_extractions"].upsert(
            {
                "chunk_id": chunk_id,
                "transcript_key": transcript_key,
                "extraction_model": model,
                "extraction_version": version,
                "warehouse_relevance": extraction.warehouse_relevance,
                "expansion_score": extraction.expansion_score,
                "move_type": extraction.move_type.value,
                "time_horizon": extraction.time_horizon.value,
                "geographic_mentions": json.dumps(
                    [g.model_dump() for g in extraction.geographic_mentions]
                ),
                "signals_json": json.dumps(
                    {
                        "signals": extraction.signals.model_dump(),
                        "sentiment": extraction.sentiment.model_dump(),
                    }
                ),
                "raw_llm_output": extraction.model_dump_json(),
                "extracted_at": datetime.now(timezone.utc).isoformat(),
            },
            pk="chunk_id",
        )

    def get_extractions_for_transcript(self, quarter_key: str) -> list[dict]:
        """Get all signal extractions for a transcript."""
        return list(
            self.db["signal_extractions"].rows_where(
                "transcript_key = ?", [quarter_key]
            )
        )

    def get_extractions_for_ticker(self, ticker: str) -> list[dict]:
        """Get all extractions across all transcripts for a ticker."""
        rows = self.db.execute(
            "SELECT se.* FROM signal_extractions se "
            "JOIN transcripts t ON se.transcript_key = t.quarter_key "
            "WHERE t.ticker = ?",
            [ticker],
        ).fetchall()
        if not rows:
            return []
        columns = [d[0] for d in self.db.execute(
            "SELECT se.* FROM signal_extractions se LIMIT 0"
        ).description]
        return [dict(zip(columns, row)) for row in rows]

    def get_tickers_with_extractions(self) -> list[str]:
        """Get all tickers that have at least one signal extraction."""
        rows = self.db.execute(
            "SELECT DISTINCT t.ticker FROM transcripts t "
            "JOIN signal_extractions se ON t.quarter_key = se.transcript_key"
        ).fetchall()
        return [r[0] for r in rows]

    # ------------------------------------------------------------------
    # Company Scores
    # ------------------------------------------------------------------

    def save_company_score(self, score: CompanyScore) -> None:
        """Save an aggregated company score."""
        self.db["company_scores"].upsert(
            {
                "ticker": score.ticker,
                "company_name": score.company_name,
                "sector": score.sector.value,
                "composite_score": score.composite_score,
                "tier": score.tier.value,
                "confidence": score.confidence,
                "avg_warehouse_relevance": score.avg_warehouse_relevance,
                "avg_expansion_score": score.avg_expansion_score,
                "max_expansion_score": score.max_expansion_score,
                "num_relevant_chunks": score.num_relevant_chunks,
                "total_chunks": score.total_chunks,
                "top_geographies": json.dumps(score.top_geographies),
                "dominant_time_horizon": score.dominant_time_horizon.value,
                "dominant_move_type": score.dominant_move_type.value,
                "has_capex_signal": int(score.has_capex_signal),
                "has_build_to_suit": int(score.has_build_to_suit),
                "has_last_mile": int(score.has_last_mile),
                "evidence_snippets": json.dumps(score.evidence_snippets),
                "transcript_keys": json.dumps(score.transcript_keys),
                "score_components_json": (
                    score.score_components.model_dump_json()
                    if score.score_components
                    else "null"
                ),
                "top_contributions_json": json.dumps(
                    [c.model_dump(mode="json") for c in score.top_contributions]
                ),
                "scored_at": score.scored_at.isoformat(),
            },
            pk="ticker",
            alter=True,
        )

    def get_all_company_scores(self) -> list[dict]:
        """Get all company scores, sorted by composite_score descending."""
        return list(
            self.db["company_scores"].rows_where(order_by="-composite_score")
        )

    def get_company_score(self, ticker: str) -> dict | None:
        """Get score for a single company."""
        try:
            return dict(self.db["company_scores"].get(ticker))
        except sqlite_utils.db.NotFoundError:
            return None

    def row_to_company_score(self, row: dict) -> CompanyScore:
        """Convert a DB row dict to a CompanyScore model."""
        components_raw = row.get("score_components_json") or "null"
        try:
            components_data = json.loads(components_raw)
        except (TypeError, json.JSONDecodeError):
            components_data = None
        components = (
            ScoreComponents(**components_data) if components_data else None
        )

        contribs_raw = row.get("top_contributions_json") or "[]"
        try:
            contribs_data = json.loads(contribs_raw)
        except (TypeError, json.JSONDecodeError):
            contribs_data = []
        contributions = [ChunkContribution(**c) for c in contribs_data]

        tier_value = row.get("tier") or SignalTier.NOISE.value
        try:
            tier = SignalTier(tier_value)
        except ValueError:
            tier = SignalTier.NOISE

        return CompanyScore(
            ticker=row["ticker"],
            company_name=row["company_name"],
            sector=Sector(row["sector"]),
            composite_score=row["composite_score"],
            tier=tier,
            confidence=row.get("confidence") or 0.0,
            avg_warehouse_relevance=row["avg_warehouse_relevance"],
            avg_expansion_score=row["avg_expansion_score"],
            max_expansion_score=row["max_expansion_score"],
            num_relevant_chunks=row["num_relevant_chunks"],
            total_chunks=row["total_chunks"],
            top_geographies=json.loads(row["top_geographies"]),
            dominant_time_horizon=TimeHorizon(row["dominant_time_horizon"]),
            dominant_move_type=MoveType(row["dominant_move_type"]),
            has_capex_signal=bool(row["has_capex_signal"]),
            has_build_to_suit=bool(row["has_build_to_suit"]),
            has_last_mile=bool(row["has_last_mile"]),
            evidence_snippets=json.loads(row["evidence_snippets"]),
            transcript_keys=json.loads(row["transcript_keys"]),
            score_components=components,
            top_contributions=contributions,
        )

    # ------------------------------------------------------------------
    # Signal Frameworks
    # ------------------------------------------------------------------

    def _seed_default_framework_if_empty(self) -> None:
        """If no frameworks exist yet, install the default seed library."""
        if self.db["signal_frameworks"].count > 0:
            return

        from warehouse_signal.scoring.tiers import DEFAULT_FRAMEWORK_SEED

        framework = DEFAULT_FRAMEWORK_SEED()
        self.save_framework(framework)

    def save_framework(self, framework: SignalFramework) -> None:
        """Upsert a framework + replace its keywords in one shot."""
        now = datetime.now(timezone.utc).isoformat()
        self.db["signal_frameworks"].upsert(
            {
                "id": framework.id,
                "name": framework.name,
                "description": framework.description,
                "is_default": int(framework.is_default),
                "boost_config_json": framework.boosts.model_dump_json(),
                "created_at": framework.created_at.isoformat(),
                "updated_at": now,
            },
            pk="id",
            alter=True,
        )
        # If is_default flipping on, clear it elsewhere
        if framework.is_default:
            for row in self.db["signal_frameworks"].rows_where(
                "is_default = 1 AND id != ?", [framework.id]
            ):
                self.db["signal_frameworks"].update(
                    row["id"], {"is_default": 0}
                )
        # Replace the keyword set for this framework
        self.db.execute(
            "DELETE FROM signal_keywords WHERE framework_id = ?",
            [framework.id],
        )
        for kw in framework.keywords:
            self._save_keyword_row(kw)

    def _save_keyword_row(self, kw: SignalKeyword) -> None:
        self.db["signal_keywords"].upsert(
            {
                "id": kw.id,
                "framework_id": kw.framework_id,
                "category": kw.category.value,
                "phrase": kw.phrase,
                "is_regex": int(kw.is_regex),
                "weight": kw.weight,
                "companion_pattern": kw.companion_pattern or "",
                "notes": kw.notes,
                "created_at": kw.created_at.isoformat(),
            },
            pk="id",
        )

    def list_frameworks(self) -> list[SignalFramework]:
        rows = list(
            self.db["signal_frameworks"].rows_where(order_by="-is_default, name")
        )
        return [self._row_to_framework(r) for r in rows]

    def get_framework(self, framework_id: str) -> SignalFramework | None:
        try:
            row = self.db["signal_frameworks"].get(framework_id)
        except sqlite_utils.db.NotFoundError:
            return None
        return self._row_to_framework(row)

    def get_default_framework(self) -> SignalFramework | None:
        rows = list(
            self.db["signal_frameworks"].rows_where(
                "is_default = 1", limit=1
            )
        )
        if not rows:
            # Fallback: any framework
            rows = list(self.db["signal_frameworks"].rows_where(limit=1))
        if not rows:
            return None
        return self._row_to_framework(rows[0])

    def _row_to_framework(self, row: dict) -> SignalFramework:
        kw_rows = list(
            self.db["signal_keywords"].rows_where(
                "framework_id = ?", [row["id"]], order_by="category, phrase"
            )
        )
        keywords = [self._row_to_keyword(k) for k in kw_rows]

        boost_raw = row.get("boost_config_json")
        if boost_raw:
            try:
                boosts = BoostConfig(**json.loads(boost_raw))
            except (json.JSONDecodeError, TypeError, ValueError):
                boosts = BoostConfig()
        else:
            boosts = BoostConfig()

        return SignalFramework(
            id=row["id"],
            name=row["name"],
            description=row.get("description") or "",
            is_default=bool(row.get("is_default")),
            keywords=keywords,
            boosts=boosts,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _row_to_keyword(self, row: dict) -> SignalKeyword:
        companion = row.get("companion_pattern") or None
        if companion == "":
            companion = None
        return SignalKeyword(
            id=row["id"],
            framework_id=row["framework_id"],
            category=KeywordCategory(row["category"]),
            phrase=row["phrase"],
            is_regex=bool(row["is_regex"]),
            weight=row["weight"],
            companion_pattern=companion,
            notes=row.get("notes") or "",
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def delete_framework(self, framework_id: str) -> None:
        self.db.execute(
            "DELETE FROM signal_keywords WHERE framework_id = ?",
            [framework_id],
        )
        self.db.execute(
            "DELETE FROM keyword_hits WHERE framework_id = ?",
            [framework_id],
        )
        try:
            self.db["signal_frameworks"].delete(framework_id)
        except sqlite_utils.db.NotFoundError:
            pass

    def add_keyword(self, kw: SignalKeyword) -> None:
        self._save_keyword_row(kw)

    def update_keyword(self, kw: SignalKeyword) -> None:
        self._save_keyword_row(kw)

    def delete_keyword(self, keyword_id: str) -> None:
        try:
            self.db["signal_keywords"].delete(keyword_id)
        except sqlite_utils.db.NotFoundError:
            pass

    # ------------------------------------------------------------------
    # Keyword Hits
    # ------------------------------------------------------------------

    def replace_keyword_hits_for_chunk(
        self, chunk_id: str, hits: list[KeywordHit]
    ) -> None:
        """Replace the hit set for a chunk (idempotent rescore)."""
        self.db.execute(
            "DELETE FROM keyword_hits WHERE chunk_id = ?", [chunk_id]
        )
        now = datetime.now(timezone.utc).isoformat()
        for hit in hits:
            self.db["keyword_hits"].insert(
                {
                    "id": str(uuid.uuid4()),
                    "keyword_id": hit.keyword_id,
                    "chunk_id": hit.chunk_id,
                    "transcript_key": hit.transcript_key,
                    "framework_id": "",  # set by caller through engine
                    "category": hit.category.value,
                    "phrase": hit.phrase,
                    "match_text": hit.match_text,
                    "match_offset": hit.match_offset,
                    "weight_contribution": hit.weight_contribution,
                    "created_at": now,
                }
            )

    def get_hits_for_transcript(self, quarter_key: str) -> list[dict]:
        return list(
            self.db["keyword_hits"].rows_where(
                "transcript_key = ?", [quarter_key]
            )
        )

    def get_hits_for_chunk(self, chunk_id: str) -> list[dict]:
        return list(
            self.db["keyword_hits"].rows_where("chunk_id = ?", [chunk_id])
        )

    # ------------------------------------------------------------------
    # Transcript Scores
    # ------------------------------------------------------------------

    def save_transcript_score(self, score: TranscriptScore) -> None:
        self.db["transcript_scores"].upsert(
            {
                "quarter_key": score.quarter_key,
                "ticker": score.ticker,
                "year": score.year,
                "quarter": score.quarter,
                "framework_id": score.framework_id,
                "composite_score": score.composite_score,
                "tier": score.tier.value,
                "confidence": score.confidence,
                "score_components_json": score.score_components.model_dump_json(),
                "top_contributions_json": json.dumps(
                    [c.model_dump(mode="json") for c in score.top_contributions]
                ),
                "keyword_hit_summary_json": json.dumps(score.keyword_hit_summary),
                "extracted_metrics_json": score.extracted_metrics.model_dump_json(),
                "num_relevant_chunks": score.num_relevant_chunks,
                "total_chunks": score.total_chunks,
                "scored_at": score.scored_at.isoformat(),
            },
            pk="quarter_key",
            alter=True,
        )

    def get_transcript_score(self, quarter_key: str) -> TranscriptScore | None:
        try:
            row = self.db["transcript_scores"].get(quarter_key)
        except sqlite_utils.db.NotFoundError:
            return None
        return self._row_to_transcript_score(row)

    def get_transcript_scores_for_ticker(
        self, ticker: str
    ) -> list[TranscriptScore]:
        rows = list(
            self.db["transcript_scores"].rows_where(
                "ticker = ?", [ticker], order_by="year, quarter"
            )
        )
        return [self._row_to_transcript_score(r) for r in rows]

    def get_all_transcript_scores(self) -> list[TranscriptScore]:
        rows = list(
            self.db["transcript_scores"].rows_where(
                order_by="-composite_score"
            )
        )
        return [self._row_to_transcript_score(r) for r in rows]

    def _row_to_transcript_score(self, row: dict) -> TranscriptScore:
        return TranscriptScore(
            quarter_key=row["quarter_key"],
            ticker=row["ticker"],
            year=row["year"],
            quarter=row["quarter"],
            framework_id=row["framework_id"],
            composite_score=row["composite_score"],
            tier=SignalTier(row["tier"]),
            confidence=row.get("confidence") or 0.0,
            score_components=ScoreComponents(
                **json.loads(row["score_components_json"] or "{}")
            ),
            top_contributions=[
                ChunkContribution(**c)
                for c in json.loads(row["top_contributions_json"] or "[]")
            ],
            keyword_hit_summary=json.loads(
                row["keyword_hit_summary_json"] or "{}"
            ),
            extracted_metrics=ExtractedMetrics(
                **json.loads(row["extracted_metrics_json"] or "{}")
            ),
            num_relevant_chunks=row["num_relevant_chunks"],
            total_chunks=row["total_chunks"],
            scored_at=datetime.fromisoformat(row["scored_at"]),
        )

    # ------------------------------------------------------------------
    # Watchlists
    # ------------------------------------------------------------------

    def save_watchlist(self, wl: Watchlist) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.db["watchlists"].upsert(
            {
                "id": wl.id,
                "name": wl.name,
                "tickers_json": json.dumps(wl.tickers),
                "created_at": wl.created_at.isoformat(),
                "updated_at": now,
            },
            pk="id",
        )

    def list_watchlists(self) -> list[Watchlist]:
        rows = list(self.db["watchlists"].rows_where(order_by="-updated_at"))
        return [self._row_to_watchlist(r) for r in rows]

    def get_watchlist(self, watchlist_id: str) -> Watchlist | None:
        try:
            row = self.db["watchlists"].get(watchlist_id)
        except sqlite_utils.db.NotFoundError:
            return None
        return self._row_to_watchlist(row)

    def delete_watchlist(self, watchlist_id: str) -> None:
        try:
            self.db["watchlists"].delete(watchlist_id)
        except sqlite_utils.db.NotFoundError:
            pass

    def _row_to_watchlist(self, row: dict) -> Watchlist:
        return Watchlist(
            id=row["id"],
            name=row["name"],
            tickers=json.loads(row["tickers_json"] or "[]"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # ------------------------------------------------------------------
    # Scan Jobs
    # ------------------------------------------------------------------

    def save_scan_job(self, job: ScanJob) -> None:
        self.db["scan_jobs"].upsert(
            {
                "id": job.id,
                "status": job.status.value,
                "params_json": json.dumps(job.params),
                "progress_json": json.dumps(job.progress),
                "results_summary_json": json.dumps(job.results_summary),
                "started_at": job.started_at.isoformat() if job.started_at else "",
                "finished_at": job.finished_at.isoformat() if job.finished_at else "",
                "error": job.error or "",
                "created_at": job.created_at.isoformat(),
            },
            pk="id",
        )

    def get_scan_job(self, job_id: str) -> ScanJob | None:
        try:
            row = self.db["scan_jobs"].get(job_id)
        except sqlite_utils.db.NotFoundError:
            return None
        return self._row_to_scan_job(row)

    def list_scan_jobs(self, limit: int = 20) -> list[ScanJob]:
        rows = list(
            self.db["scan_jobs"].rows_where(order_by="-created_at", limit=limit)
        )
        return [self._row_to_scan_job(r) for r in rows]

    def _row_to_scan_job(self, row: dict) -> ScanJob:
        def _parse_dt(value: str | None):
            if not value:
                return None
            try:
                return datetime.fromisoformat(value)
            except (TypeError, ValueError):
                return None

        return ScanJob(
            id=row["id"],
            status=ScanJobStatus(row["status"]),
            params=json.loads(row["params_json"] or "{}"),
            progress=json.loads(row["progress_json"] or "{}"),
            results_summary=json.loads(row["results_summary_json"] or "{}"),
            started_at=_parse_dt(row.get("started_at")),
            finished_at=_parse_dt(row.get("finished_at")),
            error=row.get("error") or None,
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        return {
            "companies": self.db["companies"].count,
            "transcripts": self.db["transcripts"].count,
            "transcripts_unprocessed": self.db.execute(
                "SELECT COUNT(*) FROM transcripts WHERE processed = 0"
            ).fetchone()[0],
            "chunks": self.db["chunks"].count,
            "signal_extractions": self.db["signal_extractions"].count,
            "company_scores": self.db["company_scores"].count,
            "transcript_scores": self.db["transcript_scores"].count,
            "frameworks": self.db["signal_frameworks"].count,
            "keyword_hits": self.db["keyword_hits"].count,
            "watchlists": self.db["watchlists"].count,
            "scan_jobs": self.db["scan_jobs"].count,
        }

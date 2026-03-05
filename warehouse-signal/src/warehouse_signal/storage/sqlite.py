"""SQLite storage backend for the MVP.

Uses sqlite-utils for convenience. Designed to be replaceable with
PostgreSQL later without changing the rest of the codebase.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import sqlite_utils

from warehouse_signal.config import Config
from warehouse_signal.models.schemas import (
    ChunkExtraction,
    Company,
    CompanyScore,
    MoveType,
    Sector,
    TimeHorizon,
    Transcript,
    TranscriptChunk,
)


class Storage:
    """SQLite-backed storage for transcripts, companies, and chunks."""

    def __init__(self, db_path: Path | str | None = None):
        path = Path(db_path or Config.DATABASE_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        import sqlite3
        conn = sqlite3.connect(str(path), check_same_thread=False)
        self.db = sqlite_utils.Database(conn)
        self._ensure_tables()

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
                    "scored_at": str,
                },
                pk="ticker",
                if_not_exists=True,
            )
            self.db["company_scores"].create_index(
                ["composite_score"], if_not_exists=True
            )

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
                "scored_at": score.scored_at.isoformat(),
            },
            pk="ticker",
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
        return CompanyScore(
            ticker=row["ticker"],
            company_name=row["company_name"],
            sector=Sector(row["sector"]),
            composite_score=row["composite_score"],
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
        }

"""Parameter-driven batch scans (Phase 3).

A scan is an async job that:
  1. Resolves a ticker list (sector, raw list, or watchlist).
  2. For each ticker: ingest transcript (FMP cache reuse), run keyword
     engine, run ClaudeAnalyzer, persist TranscriptScore + CompanyScore.
  3. Streams progress events over SSE.

The runner currently uses FastAPI's BackgroundTasks. For heavier loads
swap to a worker process — the API surface stays the same.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator, Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from warehouse_signal.analysis.concept_engine import detect as detect_concepts
from warehouse_signal.analysis.embeddings import NullEmbedder, get_embedder
from warehouse_signal.analysis.extractor import ClaudeAnalyzer
from warehouse_signal.analysis.keyword_engine import compile_framework, detect
from warehouse_signal.api.deps import get_storage
from warehouse_signal.config import Config
from warehouse_signal.ingestion.parser import chunk_transcript, parse_sections
from warehouse_signal.ingestion.pipeline import ingest_transcript
from warehouse_signal.models.schemas import (
    ScanJob,
    ScanJobStatus,
    Sector,
    SignalFramework,
    TranscriptChunk,
    SectionType,
)
from warehouse_signal.providers.fmp import FMPProvider
from warehouse_signal.scoring.aggregator import score_company, score_transcript
from warehouse_signal.universe.sp500 import fetch_sp500_tickers

router = APIRouter(prefix="/scans", tags=["scans"])


# ---------------------------------------------------------------------------
# Event bus — in-memory, per-job asyncio.Queue for SSE consumers
# ---------------------------------------------------------------------------

_event_queues: dict[str, asyncio.Queue] = {}
_completion_flags: dict[str, asyncio.Event] = {}


def _publish(job_id: str, event: dict) -> None:
    queue = _event_queues.get(job_id)
    if queue is not None:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass


def _complete(job_id: str) -> None:
    flag = _completion_flags.get(job_id)
    if flag is not None:
        flag.set()


# ---------------------------------------------------------------------------
# Request shapes
# ---------------------------------------------------------------------------

class ScanByTickers(BaseModel):
    mode: Literal["tickers"]
    tickers: list[str]
    year: int
    quarter: int = Field(ge=1, le=4)
    framework_id: str | None = None


class ScanBySector(BaseModel):
    mode: Literal["sector"]
    sectors: list[str]
    year: int
    quarter: int = Field(ge=1, le=4)
    max_companies: int = Field(default=25, ge=1, le=100)
    framework_id: str | None = None


class ScanByWatchlist(BaseModel):
    mode: Literal["watchlist"]
    watchlist_id: str
    year: int
    quarter: int = Field(ge=1, le=4)
    framework_id: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", status_code=202)
async def start_scan(
    payload: dict, background_tasks: BackgroundTasks
) -> dict:
    """Accept any of three mode shapes and kick off a job."""
    mode = payload.get("mode")
    if mode not in ("tickers", "sector", "watchlist"):
        raise HTTPException(
            400, "mode must be one of: 'tickers', 'sector', 'watchlist'"
        )

    storage = get_storage()
    framework = (
        storage.get_framework(payload.get("framework_id"))
        if payload.get("framework_id")
        else storage.get_default_framework()
    )
    if framework is None:
        raise HTTPException(404, "Framework not found")

    tickers = await _resolve_tickers(payload, mode, storage)
    if not tickers:
        raise HTTPException(400, "Resolved ticker list is empty")
    if len(tickers) > Config.SCAN_MAX_COMPANIES:
        tickers = tickers[: Config.SCAN_MAX_COMPANIES]

    year = int(payload["year"])
    quarter = int(payload["quarter"])

    job = ScanJob(
        id=str(uuid.uuid4()),
        status=ScanJobStatus.PENDING,
        params={
            "mode": mode,
            "tickers": tickers,
            "year": year,
            "quarter": quarter,
            "framework_id": framework.id,
        },
        progress={"completed": 0, "total": len(tickers), "events": []},
        results_summary={"scored": [], "skipped": []},
        created_at=datetime.now(timezone.utc),
    )
    storage.save_scan_job(job)
    _event_queues[job.id] = asyncio.Queue(maxsize=10_000)
    _completion_flags[job.id] = asyncio.Event()

    background_tasks.add_task(_run_scan, job.id, tickers, year, quarter, framework)
    return {"job_id": job.id, "ticker_count": len(tickers)}


@router.get("")
def list_scans() -> list[dict]:
    return [j.model_dump(mode="json") for j in get_storage().list_scan_jobs()]


@router.get("/{job_id}")
def get_scan(job_id: str) -> dict:
    job = get_storage().get_scan_job(job_id)
    if not job:
        raise HTTPException(404, f"Scan job {job_id} not found")
    return job.model_dump(mode="json")


@router.get("/{job_id}/stream")
async def stream_scan(job_id: str) -> StreamingResponse:
    storage = get_storage()
    job = storage.get_scan_job(job_id)
    if not job:
        raise HTTPException(404, f"Scan job {job_id} not found")

    queue = _event_queues.get(job_id)
    flag = _completion_flags.get(job_id)

    async def gen() -> AsyncIterator[str]:
        # Replay anything we've already accumulated on the job row.
        for event in job.progress.get("events", []):
            yield _sse(event)
        if job.status in (ScanJobStatus.COMPLETED, ScanJobStatus.FAILED, ScanJobStatus.CANCELED):
            yield _sse({"type": "done", "status": job.status.value})
            return
        if queue is None or flag is None:
            yield _sse(
                {
                    "type": "error",
                    "message": "Server lost track of this job — try GET /scans/{id} for status.",
                }
            )
            return
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15.0)
                yield _sse(event)
                if event.get("type") == "done":
                    return
            except asyncio.TimeoutError:
                if flag.is_set():
                    return
                # Heartbeat
                yield ":\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

async def _resolve_tickers(payload: dict, mode: str, storage) -> list[str]:
    if mode == "tickers":
        return [t.strip().upper() for t in payload.get("tickers", []) if t.strip()]

    if mode == "watchlist":
        wid = payload.get("watchlist_id")
        if not wid:
            return []
        wl = storage.get_watchlist(wid)
        return list(wl.tickers) if wl else []

    if mode == "sector":
        sector_values = payload.get("sectors") or []
        valid: set[Sector] = set()
        for sv in sector_values:
            try:
                valid.add(Sector(sv))
            except ValueError:
                continue
        if not valid:
            return []
        all_companies = await fetch_sp500_tickers()
        return [c.ticker for c in all_companies if c.sector in valid]

    return []


async def _run_scan(
    job_id: str,
    tickers: list[str],
    year: int,
    quarter: int,
    framework: SignalFramework,
) -> None:
    storage = get_storage()
    job = storage.get_scan_job(job_id)
    if job is None:
        return

    job.status = ScanJobStatus.RUNNING
    job.started_at = datetime.now(timezone.utc)
    storage.save_scan_job(job)
    _publish(job_id, {"type": "started", "total": len(tickers)})

    provider = FMPProvider() if Config.FMP_API_KEY else None
    analyzer = ClaudeAnalyzer() if Config.ANTHROPIC_API_KEY else None
    compiled = compile_framework(framework)

    scored: list[dict] = []
    skipped: list[dict] = []

    try:
        for index, ticker in enumerate(tickers):
            _emit_event(
                storage, job, {"type": "progress", "ticker": ticker, "phase": "ingest", "index": index}
            )

            quarter_key = f"{ticker}_{year}Q{quarter}"
            ingested = False
            if not storage.has_transcript(ticker, year, quarter):
                if provider is None:
                    _emit_event(
                        storage,
                        job,
                        {
                            "type": "skip",
                            "ticker": ticker,
                            "reason": "FMP_API_KEY not configured",
                        },
                    )
                    skipped.append({"ticker": ticker, "reason": "no provider"})
                    continue
                try:
                    transcript = await ingest_transcript(
                        provider, storage, ticker, year, quarter
                    )
                    if not transcript:
                        skipped.append({"ticker": ticker, "reason": "no transcript"})
                        _emit_event(
                            storage,
                            job,
                            {"type": "skip", "ticker": ticker, "reason": "no transcript"},
                        )
                        continue
                    ingested = True
                except Exception as e:  # noqa: BLE001
                    skipped.append({"ticker": ticker, "reason": f"ingest error: {e}"})
                    _emit_event(
                        storage,
                        job,
                        {"type": "skip", "ticker": ticker, "reason": str(e)},
                    )
                    continue

            chunks_rows = storage.get_chunks_for_transcript(quarter_key)
            if not chunks_rows:
                skipped.append({"ticker": ticker, "reason": "no chunks"})
                continue

            chunks = [
                TranscriptChunk(
                    chunk_id=row["chunk_id"],
                    transcript_key=row["transcript_key"],
                    chunk_index=row["chunk_index"],
                    text=row["text"],
                    section_type=SectionType(row["section_type"]),
                    speaker=row.get("speaker"),
                    speaker_role=row.get("speaker_role"),
                    token_estimate=row.get("token_estimate") or 0,
                )
                for row in chunks_rows
            ]

            _emit_event(
                storage,
                job,
                {"type": "progress", "ticker": ticker, "phase": "keyword"},
            )
            for chunk in chunks:
                hits = detect(chunk, framework, compiled=compiled)
                storage.replace_keyword_hits_for_chunk(chunk.chunk_id, hits)

            # Concepts: only when the framework defines them AND embedder configured
            if framework.concepts:
                embedder = get_embedder()
                if not isinstance(embedder, NullEmbedder):
                    _emit_event(
                        storage,
                        job,
                        {"type": "progress", "ticker": ticker, "phase": "concept"},
                    )
                    for chunk in chunks:
                        vec = storage.get_chunk_embedding(chunk.chunk_id)
                        if not vec:
                            try:
                                vec = embedder.embed(chunk.text)
                            except Exception as e:  # noqa: BLE001
                                _emit_event(
                                    storage,
                                    job,
                                    {
                                        "type": "warn",
                                        "ticker": ticker,
                                        "message": f"embed error: {e}",
                                    },
                                )
                                vec = []
                            if vec:
                                storage.save_chunk_embedding(chunk.chunk_id, vec)
                        if not vec:
                            continue
                        c_hits = detect_concepts(
                            chunk, framework.concepts, vec, embedder=embedder
                        )
                        storage.replace_concept_hits_for_chunk(
                            chunk.chunk_id, framework.id, c_hits
                        )

            _emit_event(
                storage,
                job,
                {"type": "progress", "ticker": ticker, "phase": "llm"},
            )
            if analyzer is not None:
                existing = {
                    e["chunk_id"]
                    for e in storage.get_extractions_for_transcript(quarter_key)
                }
                company_name = storage.get_company_name(ticker)
                for chunk in chunks:
                    if chunk.chunk_id in existing:
                        continue
                    try:
                        extraction = await analyzer.extract_signals(
                            chunk, ticker, company_name, year, quarter
                        )
                        storage.save_extraction(
                            chunk.chunk_id,
                            quarter_key,
                            analyzer.name,
                            Config.EXTRACTION_VERSION,
                            extraction,
                        )
                    except Exception as e:  # noqa: BLE001
                        _emit_event(
                            storage,
                            job,
                            {
                                "type": "warn",
                                "ticker": ticker,
                                "message": f"LLM error on chunk {chunk.chunk_index}: {e}",
                            },
                        )

            _emit_event(
                storage,
                job,
                {"type": "progress", "ticker": ticker, "phase": "score"},
            )
            score = score_transcript(storage, quarter_key, framework)
            if score is not None:
                storage.save_transcript_score(score)
                company = score_company(storage, ticker)
                if company:
                    storage.save_company_score(company)
                scored.append(
                    {
                        "ticker": ticker,
                        "quarter_key": quarter_key,
                        "composite": score.composite_score,
                        "tier": score.tier.value,
                    }
                )
                _emit_event(
                    storage,
                    job,
                    {
                        "type": "scored",
                        "ticker": ticker,
                        "quarter_key": quarter_key,
                        "composite": score.composite_score,
                        "tier": score.tier.value,
                        "ingested": ingested,
                    },
                )

            job.progress["completed"] = index + 1
            storage.save_scan_job(job)

        job.status = ScanJobStatus.COMPLETED
        job.finished_at = datetime.now(timezone.utc)
        job.results_summary = {"scored": scored, "skipped": skipped}
        storage.save_scan_job(job)
        _publish(job_id, {"type": "done", "scored": len(scored), "skipped": len(skipped)})

    except Exception as e:  # noqa: BLE001
        job.status = ScanJobStatus.FAILED
        job.finished_at = datetime.now(timezone.utc)
        job.error = str(e)
        storage.save_scan_job(job)
        _publish(job_id, {"type": "error", "message": str(e)})

    finally:
        if provider is not None:
            await provider.close()
        if analyzer is not None:
            await analyzer.close()
        _complete(job_id)


def _emit_event(storage, job: ScanJob, event: dict) -> None:
    """Append the event to the job row's history AND publish over SSE."""
    job.progress.setdefault("events", []).append(event)
    storage.save_scan_job(job)
    _publish(job.id, event)


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"

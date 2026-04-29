"""Manual transcript upload + score-refresh endpoints.

Accepts text or PDF, runs the existing parse → chunk pipeline, persists
with provider="upload". A separate /score endpoint runs keyword detection
+ LLM extraction + hybrid scoring against the cached chunks.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from warehouse_signal.analysis.concept_engine import detect as detect_concepts
from warehouse_signal.analysis.embeddings import NullEmbedder, get_embedder
from warehouse_signal.analysis.extractor import ClaudeAnalyzer
from warehouse_signal.analysis.keyword_engine import compile_framework, detect
from warehouse_signal.api.deps import get_storage
from warehouse_signal.config import Config
from warehouse_signal.ingestion.extract_pdf import (
    PdfExtractionError,
    pdf_bytes_to_text,
)
from warehouse_signal.ingestion.parser import chunk_transcript, parse_sections
from warehouse_signal.models.schemas import (
    Company,
    Sector,
    Transcript,
    TranscriptMetadata,
)
from warehouse_signal.scoring.aggregator import score_company, score_transcript

router = APIRouter(prefix="/transcripts", tags=["transcripts"])

# Hard cap on raw text after PDF→text conversion.
MAX_RAW_TEXT_BYTES = 200_000


class UploadResponse(BaseModel):
    quarter_key: str
    ticker: str
    year: int
    quarter: int
    raw_text_length: int
    chunk_count: int
    sections_detected: bool


@router.post("/upload", response_model=UploadResponse)
async def upload_transcript(
    ticker: str = Form(...),
    company_name: str = Form(...),
    year: int = Form(...),
    quarter: int = Form(...),
    sector: str = Form("other"),
    raw_text: str | None = Form(None),
    file: UploadFile | None = File(None),
) -> UploadResponse:
    """Accept a transcript via paste, .txt, or .pdf and persist it."""
    text = (raw_text or "").strip()

    if file is not None:
        data = await file.read()
        filename = (file.filename or "").lower()
        if filename.endswith(".pdf") or (file.content_type or "").endswith("pdf"):
            try:
                text = pdf_bytes_to_text(data)
            except PdfExtractionError as e:
                raise HTTPException(status_code=400, detail=str(e))
        else:
            try:
                text = data.decode("utf-8", errors="replace").strip()
            except Exception as e:  # noqa: BLE001
                raise HTTPException(
                    status_code=400, detail=f"Could not read file: {e}"
                )

    if not text:
        raise HTTPException(
            status_code=400,
            detail="Provide either raw_text or a .txt/.pdf file with content.",
        )

    if len(text.encode("utf-8")) > MAX_RAW_TEXT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Transcript exceeds the {MAX_RAW_TEXT_BYTES // 1000}KB cap. "
                "Trim or split before uploading."
            ),
        )

    if quarter not in (1, 2, 3, 4):
        raise HTTPException(status_code=400, detail="quarter must be 1..4")

    storage = get_storage()
    ticker = ticker.strip().upper()

    try:
        sector_enum = Sector(sector)
    except ValueError:
        sector_enum = Sector.OTHER

    storage.upsert_company(
        Company(ticker=ticker, name=company_name, sector=sector_enum)
    )

    transcript = Transcript(
        metadata=TranscriptMetadata(
            ticker=ticker,
            year=year,
            quarter=quarter,
            provider="upload",
        ),
        raw_text=text,
        sections=[],
        fetched_at=datetime.now(timezone.utc),
    )

    parse_sections(transcript)
    chunks = chunk_transcript(transcript)

    storage.save_transcript(transcript)
    storage.save_chunks(chunks)

    return UploadResponse(
        quarter_key=transcript.quarter_key,
        ticker=ticker,
        year=year,
        quarter=quarter,
        raw_text_length=len(text),
        chunk_count=len(chunks),
        sections_detected=transcript.has_sections,
    )


class ScoreRefreshRequest(BaseModel):
    framework_id: str | None = None
    run_keyword_engine: bool = True
    run_llm: bool = False  # Off by default — costs money; user opts in.


@router.post("/{quarter_key}/score")
async def refresh_transcript_score(
    quarter_key: str, req: ScoreRefreshRequest = ScoreRefreshRequest()
) -> dict:
    """Compute (or recompute) a transcript's score.

    - If `run_keyword_engine` is on, re-runs detection per chunk and
      replaces the keyword_hits rows for those chunks.
    - If `run_llm` is on, calls ClaudeAnalyzer for any chunks that don't
      yet have an extraction (or for all of them — we keep it simple
      and only fill missing ones).
    - Always recomputes the TranscriptScore from current rows and
      persists it.
    """
    storage = get_storage()

    framework = (
        storage.get_framework(req.framework_id)
        if req.framework_id
        else storage.get_default_framework()
    )
    if framework is None:
        raise HTTPException(404, "Framework not found")

    chunks_rows = storage.get_chunks_for_transcript(quarter_key)
    if not chunks_rows:
        raise HTTPException(404, f"No chunks for {quarter_key}")

    # Reconstruct minimal TranscriptChunk objects for engine + analyzer
    from warehouse_signal.models.schemas import (
        SectionType,
        TranscriptChunk,
    )

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

    if req.run_keyword_engine:
        compiled = compile_framework(framework)
        for chunk in chunks:
            hits = detect(chunk, framework, compiled=compiled)
            storage.replace_keyword_hits_for_chunk(chunk.chunk_id, hits)

        # Concept detection: only when the framework has concepts AND an
        # embedder is configured. NullEmbedder = silently skip.
        if framework.concepts:
            embedder = get_embedder()
            if not isinstance(embedder, NullEmbedder):
                for chunk in chunks:
                    vec = storage.get_chunk_embedding(chunk.chunk_id)
                    if not vec:
                        vec = embedder.embed(chunk.text)
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

    if req.run_llm:
        if not Config.ANTHROPIC_API_KEY:
            raise HTTPException(
                status_code=400,
                detail="ANTHROPIC_API_KEY is not set; cannot run LLM extraction.",
            )
        existing = {
            e["chunk_id"]
            for e in storage.get_extractions_for_transcript(quarter_key)
        }
        analyzer = ClaudeAnalyzer()
        try:
            company_name = storage.get_company_name(chunks[0].transcript_key.split("_")[0])
            year = int(quarter_key.split("_")[1][:4])
            quarter = int(quarter_key.split("Q")[1])
            ticker = quarter_key.split("_")[0]
            for chunk in chunks:
                if chunk.chunk_id in existing:
                    continue
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
        finally:
            await analyzer.close()

    score = score_transcript(storage, quarter_key, framework)
    if score is None:
        raise HTTPException(404, f"Could not score transcript {quarter_key}")
    storage.save_transcript_score(score)

    # Refresh company-level rollup so /radar reflects the new transcript.
    company = score_company(storage, score.ticker)
    if company:
        storage.save_company_score(company)

    return score.model_dump(mode="json")

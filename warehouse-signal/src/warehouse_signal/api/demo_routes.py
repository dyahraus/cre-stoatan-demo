"""Demo pipeline walkthrough endpoints with SSE streaming for LLM extraction."""

from __future__ import annotations

import json

import anthropic
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from warehouse_signal.analysis.extractor import _parse_json
from warehouse_signal.analysis.prompt import format_extraction_prompt, format_system_prompt
from warehouse_signal.api.deps import get_storage
from warehouse_signal.config import Config
from warehouse_signal.ingestion.parser import parse_sections, chunk_transcript
from warehouse_signal.ingestion.pipeline import ingest_transcript
from warehouse_signal.models.schemas import (
    CallTiming,
    ChunkExtraction,
    Company,
    SectionType,
    Sector,
    Transcript,
    TranscriptMetadata,
    TranscriptSection,
)
from warehouse_signal.providers.fmp import FMPProvider
from warehouse_signal.scoring.aggregator import (
    RELEVANCE_THRESHOLD,
    TIME_WEIGHTS,
    compute_composite_score,
)

router = APIRouter(prefix="/demo", tags=["demo"])

# Hardcoded demo transcripts — fetched from FMP once, then cached in DB
DEMO_TRANSCRIPTS = [
    ("PLD", "Prologis Inc", 2024, 3, Sector.REIT_INDUSTRIAL),
    ("WMT", "Walmart Inc", 2024, 3, Sector.RETAIL),
    ("HD", "The Home Depot", 2024, 3, Sector.RETAIL),
]


def _reconstruct_transcript(row: dict) -> Transcript:
    """Reconstruct a Transcript pydantic model from a DB row."""
    sections_data = json.loads(row.get("sections_json", "[]"))
    sections = [
        TranscriptSection(
            section_type=SectionType(s["section_type"]),
            speaker=s.get("speaker"),
            speaker_role=s.get("speaker_role"),
            text=s["text"],
        )
        for s in sections_data
    ]
    return Transcript(
        metadata=TranscriptMetadata(
            ticker=row["ticker"],
            year=row["year"],
            quarter=row["quarter"],
            call_date=row.get("call_date"),
            provider=row.get("provider", "fmp"),
        ),
        raw_text=row["raw_text"],
        sections=sections,
    )


# ------------------------------------------------------------------
# 1. List / ensure demo transcripts
# ------------------------------------------------------------------


@router.get("/transcripts")
async def demo_transcripts() -> list[dict]:
    """List the 3 demo transcripts, fetching from FMP if not cached."""
    storage = get_storage()
    results = []
    need_fetch = []

    for ticker, name, year, quarter, sector in DEMO_TRANSCRIPTS:
        key = f"{ticker}_{year}Q{quarter}"
        has_real = False
        if storage.has_transcript(ticker, year, quarter):
            row = storage.db["transcripts"].get(key)
            # Only use cached transcript if it's from a real provider (not mock)
            if row.get("provider") == "fmp" and len(row["raw_text"]) > 5000:
                has_real = True
                results.append({
                    "ticker": ticker,
                    "company_name": name,
                    "year": year,
                    "quarter": quarter,
                    "quarter_key": key,
                    "raw_text_length": len(row["raw_text"]),
                    "call_date": row.get("call_date"),
                })
        if not has_real:
            need_fetch.append((ticker, name, year, quarter, sector))

    if need_fetch:
        provider = FMPProvider()
        try:
            for ticker, name, year, quarter, sector in need_fetch:
                transcript = await ingest_transcript(
                    provider, storage, ticker, year, quarter, force=True
                )
                if transcript:
                    storage.upsert_company(
                        Company(ticker=ticker, name=name, sector=sector)
                    )
                    results.append({
                        "ticker": ticker,
                        "company_name": name,
                        "year": year,
                        "quarter": quarter,
                        "quarter_key": transcript.quarter_key,
                        "raw_text_length": len(transcript.raw_text),
                        "call_date": (
                            transcript.metadata.call_date.isoformat()
                            if transcript.metadata.call_date
                            else None
                        ),
                    })
                else:
                    results.append({
                        "ticker": ticker,
                        "company_name": name,
                        "year": year,
                        "quarter": quarter,
                        "quarter_key": f"{ticker}_{year}Q{quarter}",
                        "raw_text_length": 0,
                        "call_date": None,
                    })
        finally:
            await provider.close()

    # Sort to match DEMO_TRANSCRIPTS order
    order = {t[0]: i for i, t in enumerate(DEMO_TRANSCRIPTS)}
    results.sort(key=lambda r: order.get(r["ticker"], 99))
    return results


# ------------------------------------------------------------------
# 2. Parse sections
# ------------------------------------------------------------------


@router.get("/parse")
def demo_parse(quarter_key: str = Query(...)) -> dict:
    """Run section parsing on a transcript and return the results."""
    storage = get_storage()
    try:
        row = storage.db["transcripts"].get(quarter_key)
    except Exception:
        raise HTTPException(404, f"Transcript {quarter_key} not found")

    transcript = _reconstruct_transcript(row)
    parsed = parse_sections(transcript)

    sections = []
    for s in parsed.sections:
        sections.append({
            "section_type": s.section_type.value,
            "text_length": len(s.text),
            "text_preview": s.text,
        })

    boundary_found = parsed.has_sections
    return {"sections": sections, "boundary_found": boundary_found}


# ------------------------------------------------------------------
# 3. Chunk transcript
# ------------------------------------------------------------------


@router.get("/chunks")
def demo_chunks(quarter_key: str = Query(...)) -> dict:
    """Return chunk breakdown for a transcript."""
    storage = get_storage()
    chunk_rows = storage.get_chunks_for_transcript(quarter_key)
    if not chunk_rows:
        raise HTTPException(404, f"No chunks found for {quarter_key}")

    chunks = []
    for c in chunk_rows:
        chunks.append({
            "chunk_index": c["chunk_index"],
            "chunk_id": c["chunk_id"],
            "section_type": c["section_type"],
            "token_estimate": c["token_estimate"],
            "text_preview": c["text"][:200],
            "text": c["text"],
        })

    total_tokens = sum(c["token_estimate"] for c in chunk_rows)
    return {
        "chunks": chunks,
        "total_chunks": len(chunks),
        "avg_tokens": total_tokens // len(chunks) if chunks else 0,
    }


# ------------------------------------------------------------------
# 4. Stream extraction via SSE
# ------------------------------------------------------------------


@router.get("/extract/stream")
async def demo_extract_stream(
    quarter_key: str = Query(...),
    chunk_index: int = Query(0),
):
    """Stream Claude's extraction of a single chunk via Server-Sent Events."""
    storage = get_storage()
    chunk_rows = storage.get_chunks_for_transcript(quarter_key)
    if not chunk_rows:
        raise HTTPException(404, f"No chunks found for {quarter_key}")

    chunk_row = None
    for c in chunk_rows:
        if c["chunk_index"] == chunk_index:
            chunk_row = c
            break
    if chunk_row is None:
        raise HTTPException(404, f"Chunk index {chunk_index} not found")

    # Look up ticker from quarter_key
    ticker = quarter_key.split("_")[0]
    company_name = storage.get_company_name(ticker)
    year = int(quarter_key.split("_")[1][:4])
    quarter = int(quarter_key.split("Q")[1])

    system_prompt = format_system_prompt(
        ticker=ticker,
        company_name=company_name,
        year=year,
        quarter=quarter,
        section_type=chunk_row["section_type"],
    )
    user_prompt = format_extraction_prompt(chunk_text=chunk_row["text"])

    async def event_generator():
        # Send chunk info
        yield _sse({
            "type": "chunk_info",
            "chunk_index": chunk_row["chunk_index"],
            "section_type": chunk_row["section_type"],
            "token_estimate": chunk_row["token_estimate"],
        })

        # Send prompt preview
        yield _sse({
            "type": "prompt",
            "system": system_prompt,
            "user_preview": user_prompt[:300] + "...",
        })

        # Stream from Claude
        if not Config.ANTHROPIC_API_KEY:
            yield _sse({"type": "error", "message": "ANTHROPIC_API_KEY not set"})
            return

        client = anthropic.AsyncAnthropic(api_key=Config.ANTHROPIC_API_KEY)
        full_text = ""

        try:
            async with client.messages.stream(
                model=Config.LLM_MODEL,
                max_tokens=Config.EXTRACTION_MAX_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            ) as stream:
                async for text in stream.text_stream:
                    full_text += text
                    yield _sse({"type": "token", "text": text})

            # Parse the complete response
            try:
                parsed = _parse_json(full_text)
                extraction = ChunkExtraction(**parsed)
                yield _sse({
                    "type": "extraction",
                    "data": json.loads(extraction.model_dump_json()),
                })
            except Exception as e:
                yield _sse({
                    "type": "error",
                    "message": f"Failed to parse extraction: {e}",
                    "raw_text": full_text,
                })

            yield _sse({"type": "done"})

        except Exception as e:
            yield _sse({"type": "error", "message": str(e)})
        finally:
            await client.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def _sse(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


# ------------------------------------------------------------------
# 5. Score from extraction
# ------------------------------------------------------------------


class ScoreRequest(BaseModel):
    quarter_key: str
    extractions: list[dict]


def _extraction_to_row(ext: dict) -> dict:
    return {
        "warehouse_relevance": ext.get("warehouse_relevance", 0),
        "expansion_score": ext.get("expansion_score", 0),
        "move_type": ext.get("move_type", "unknown"),
        "time_horizon": ext.get("time_horizon", "unspecified"),
        "signals_json": json.dumps({
            "signals": ext.get("signals", {}),
            "sentiment": ext.get("sentiment", {}),
        }),
        "geographic_mentions": json.dumps(
            ext.get("geographic_mentions", [])
        ),
    }


@router.post("/score")
def demo_score(req: ScoreRequest) -> dict:
    """Compute a score preview from one or more chunk extractions."""
    if not req.extractions:
        raise HTTPException(status_code=400, detail="At least one extraction required")

    rows = [_extraction_to_row(ext) for ext in req.extractions]
    composite = compute_composite_score(rows)
    n = len(rows)

    # Use first extraction for summary display, but aggregate scores
    first = req.extractions[0]
    max_expansion = max(r["expansion_score"] for r in rows)
    relevant_rows = [r for r in rows if r["warehouse_relevance"] >= RELEVANCE_THRESHOLD]
    is_relevant = len(relevant_rows) > 0

    # Weighted average across relevant rows
    if relevant_rows:
        weighted_avg = sum(r["warehouse_relevance"] * r["expansion_score"] for r in relevant_rows) / sum(r["warehouse_relevance"] for r in relevant_rows)
    else:
        weighted_avg = 0

    # Aggregate flags across all extractions
    has_capex = any(bool(ext.get("signals", {}).get("capex_expansion")) for ext in req.extractions)
    has_bts = any(bool(ext.get("signals", {}).get("build_to_suit")) for ext in req.extractions)
    has_lm = any(bool(ext.get("signals", {}).get("last_mile_expansion")) for ext in req.extractions)
    flag_bonus = 0.05 * sum([has_capex, has_bts, has_lm])

    # Best time horizon
    time_horizons = [r["time_horizon"] for r in rows]
    best_th = max(time_horizons, key=lambda th: TIME_WEIGHTS.get(th, 0.2))
    time_weight = TIME_WEIGHTS.get(best_th, 0.2)

    note = (
        f"Score computed from {n} chunk{'s' if n > 1 else ''}."
        if n > 1
        else "This score is from a single chunk. The full pipeline aggregates all chunks in a transcript for a more robust composite score."
    )

    return {
        "composite_score": composite,
        "is_relevant": is_relevant,
        "components": {
            "max_expansion": {"weight": 0.40, "value": max_expansion if is_relevant else 0, "contribution": 0.40 * max_expansion if is_relevant else 0},
            "weighted_avg": {"weight": 0.30, "value": weighted_avg if is_relevant else 0, "contribution": 0.30 * weighted_avg if is_relevant else 0},
            "flag_bonus": {"weight": 0.15, "value": flag_bonus, "contribution": 0.15 * flag_bonus, "flags": {"capex": has_capex, "build_to_suit": has_bts, "last_mile": has_lm}},
            "time_bonus": {"weight": 0.15, "value": time_weight, "contribution": 0.15 * time_weight, "time_horizon": best_th},
        },
        "extraction_summary": {
            "warehouse_relevance": rows[0]["warehouse_relevance"],
            "expansion_score": rows[0]["expansion_score"],
            "move_type": rows[0]["move_type"],
            "time_horizon": rows[0]["time_horizon"],
            "evidence_quote": first.get("evidence_quote", ""),
        },
        "note": note,
    }

"""Tests for signal extraction pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from warehouse_signal.analysis.mock import MockAnalyzer
from warehouse_signal.analysis.pipeline import analyze_transcript
from warehouse_signal.config import Config
from warehouse_signal.ingestion.pipeline import ingest_transcript
from warehouse_signal.models.schemas import (
    ChunkExtraction,
    MoveType,
    SectionType,
    TimeHorizon,
    TranscriptChunk,
)
from warehouse_signal.providers.mock import MockProvider
from warehouse_signal.storage.sqlite import Storage


@pytest.fixture
def provider():
    return MockProvider()


@pytest.fixture
def analyzer():
    return MockAnalyzer()


@pytest.fixture
def storage(tmp_path):
    return Storage(db_path=tmp_path / "test.db")


# ---------------------------------------------------------------------------
# Mock analyzer tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mock_analyzer_high_signal(analyzer):
    chunk = TranscriptChunk(
        chunk_id="test_high",
        transcript_key="PLD_2024Q3",
        chunk_index=0,
        text=(
            "We broke ground on two new distribution centers this quarter. "
            "Our logistics capex is $180 million for 2.4 million square feet "
            "of new warehouse capacity. We have build-to-suit projects in the "
            "Inland Empire and Dallas Fort Worth. Last mile fulfillment is growing."
        ),
        section_type=SectionType.PREPARED_REMARKS,
        token_estimate=50,
    )
    result = await analyzer.extract_signals(chunk, "PLD", "Prologis", 2024, 3)
    assert result.warehouse_relevance >= 0.5
    assert result.expansion_score >= 0.4
    assert result.move_type == MoveType.EXPANSION


@pytest.mark.asyncio
async def test_mock_analyzer_low_signal(analyzer):
    chunk = TranscriptChunk(
        chunk_id="test_low",
        transcript_key="AAPL_2024Q3",
        chunk_index=0,
        text=(
            "Revenue came in at $4.2 billion, up 6% year over year. "
            "Gross margin expanded 40 basis points. We returned $350 million "
            "to shareholders through dividends and share repurchases."
        ),
        section_type=SectionType.PREPARED_REMARKS,
        token_estimate=30,
    )
    result = await analyzer.extract_signals(chunk, "AAPL", "Apple", 2024, 3)
    assert result.warehouse_relevance < 0.3
    assert result.expansion_score < 0.3


# ---------------------------------------------------------------------------
# Pydantic model tests
# ---------------------------------------------------------------------------

def test_chunk_extraction_validation():
    ext = ChunkExtraction(warehouse_relevance=0.8, expansion_score=0.6)
    assert ext.move_type == MoveType.UNKNOWN
    assert ext.time_horizon == TimeHorizon.UNSPECIFIED


def test_chunk_extraction_rejects_out_of_range():
    with pytest.raises(Exception):
        ChunkExtraction(warehouse_relevance=1.5, expansion_score=0.5)


def test_chunk_extraction_round_trip():
    ext = ChunkExtraction(
        warehouse_relevance=0.85,
        expansion_score=0.7,
        move_type=MoveType.EXPANSION,
        reasoning="Test round trip",
    )
    json_str = ext.model_dump_json()
    restored = ChunkExtraction.model_validate_json(json_str)
    assert restored.warehouse_relevance == ext.warehouse_relevance
    assert restored.move_type == ext.move_type


# ---------------------------------------------------------------------------
# Storage tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_save_and_load_extraction(provider, analyzer, storage):
    # Ingest a transcript first
    transcript = await provider.get_transcript("PLD", 2024, 3)
    from warehouse_signal.ingestion.parser import chunk_transcript
    storage.save_transcript(transcript)
    chunks = chunk_transcript(transcript)
    storage.save_chunks(chunks)

    # Analyze and save
    chunk = chunks[0]
    extraction = await analyzer.extract_signals(chunk, "PLD", "Prologis", 2024, 3)
    storage.save_extraction(chunk.chunk_id, "PLD_2024Q3", "mock", "v1.0", extraction)

    # Load back
    loaded = storage.get_extractions_for_transcript("PLD_2024Q3")
    assert len(loaded) == 1
    assert loaded[0]["chunk_id"] == chunk.chunk_id
    assert loaded[0]["warehouse_relevance"] == extraction.warehouse_relevance


# ---------------------------------------------------------------------------
# Pipeline tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analyze_transcript_pipeline(provider, analyzer, storage):
    """End-to-end: ingest → analyze → verify extractions + processed flag."""
    result = await ingest_transcript(provider, storage, "PLD", 2024, 3)
    assert result is not None

    # Transcript should be unprocessed
    unprocessed = storage.get_unprocessed_transcripts()
    assert len(unprocessed) == 1

    # Analyze it
    row = unprocessed[0]
    count = await analyze_transcript(analyzer, storage, row)
    assert count > 0

    # Should now be processed
    unprocessed = storage.get_unprocessed_transcripts()
    assert len(unprocessed) == 0

    # Extractions should exist
    stats = storage.get_stats()
    assert stats["signal_extractions"] > 0


@pytest.mark.asyncio
async def test_analyze_all_unprocessed(provider, analyzer, storage):
    """Ingest multiple transcripts, analyze all, verify all processed."""
    from warehouse_signal.analysis.pipeline import analyze_all_unprocessed

    await ingest_transcript(provider, storage, "PLD", 2024, 3)
    await ingest_transcript(provider, storage, "AMZN", 2024, 4)
    await ingest_transcript(provider, storage, "WMT", 2024, 4)

    results = await analyze_all_unprocessed(analyzer, storage)
    assert len(results) == 3
    assert all(v > 0 for v in results.values())

    unprocessed = storage.get_unprocessed_transcripts()
    assert len(unprocessed) == 0

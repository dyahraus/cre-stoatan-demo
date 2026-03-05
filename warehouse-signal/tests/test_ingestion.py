"""Tests for the ingestion pipeline."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from warehouse_signal.models.schemas import SectionType
from warehouse_signal.providers.mock import MockProvider
from warehouse_signal.ingestion.parser import chunk_transcript, parse_sections
from warehouse_signal.storage.sqlite import Storage


@pytest.fixture
def provider():
    return MockProvider()


@pytest.fixture
def storage(tmp_path):
    return Storage(db_path=tmp_path / "test.db")


# ---------------------------------------------------------------------------
# Provider tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mock_provider_returns_transcript(provider):
    transcript = await provider.get_transcript("PLD", 2024, 3)
    assert transcript is not None
    assert transcript.metadata.ticker == "PLD"
    assert transcript.metadata.year == 2024
    assert transcript.metadata.quarter == 3
    assert len(transcript.raw_text) > 100


@pytest.mark.asyncio
async def test_mock_provider_high_signal_for_known_tickers(provider):
    pld = await provider.get_transcript("PLD", 2024, 3)
    assert "distribution center" in pld.raw_text.lower() or "warehouse" in pld.raw_text.lower()


@pytest.mark.asyncio
async def test_mock_provider_list_transcripts(provider):
    available = await provider.list_available_transcripts("AAPL")
    assert len(available) == 16  # 4 years × 4 quarters


@pytest.mark.asyncio
async def test_mock_provider_calendar(provider):
    events = await provider.get_earnings_calendar()
    assert len(events) > 0
    assert events[0].ticker == "PLD"


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_section_parsing_already_segmented(provider):
    """Mock provider returns pre-segmented data — parser should not re-split."""
    transcript = await provider.get_transcript("PLD", 2024, 3)
    assert transcript.has_sections  # Mock provides sections
    parse_sections(transcript)  # Should be a no-op
    assert transcript.sections[0].section_type == SectionType.PREPARED_REMARKS


@pytest.mark.asyncio
async def test_chunking_produces_chunks(provider):
    transcript = await provider.get_transcript("PLD", 2024, 3)
    chunks = chunk_transcript(transcript, target_tokens=200, max_tokens=400)
    assert len(chunks) > 0
    for chunk in chunks:
        assert chunk.transcript_key == "PLD_2024Q3"
        assert chunk.text
        assert chunk.token_estimate > 0


@pytest.mark.asyncio
async def test_chunk_ids_are_deterministic(provider):
    transcript = await provider.get_transcript("PLD", 2024, 3)
    chunks_1 = chunk_transcript(transcript, target_tokens=200)
    chunks_2 = chunk_transcript(transcript, target_tokens=200)
    assert [c.chunk_id for c in chunks_1] == [c.chunk_id for c in chunks_2]


# ---------------------------------------------------------------------------
# Storage tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_storage_round_trip(provider, storage):
    transcript = await provider.get_transcript("PLD", 2024, 3)
    chunks = chunk_transcript(transcript)

    # Save
    storage.save_transcript(transcript)
    storage.save_chunks(chunks)

    # Check existence
    assert storage.has_transcript("PLD", 2024, 3)
    assert not storage.has_transcript("PLD", 2024, 2)

    # Stats
    stats = storage.get_stats()
    assert stats["transcripts"] == 1
    assert stats["chunks"] == len(chunks)


@pytest.mark.asyncio
async def test_storage_unprocessed_tracking(provider, storage):
    transcript = await provider.get_transcript("PLD", 2024, 3)
    storage.save_transcript(transcript)

    unprocessed = storage.get_unprocessed_transcripts()
    assert len(unprocessed) == 1
    assert unprocessed[0]["quarter_key"] == "PLD_2024Q3"

    storage.mark_processed("PLD_2024Q3")
    unprocessed = storage.get_unprocessed_transcripts()
    assert len(unprocessed) == 0


@pytest.mark.asyncio
async def test_storage_upsert_companies(storage):
    from warehouse_signal.models.schemas import Company, Sector
    companies = [
        Company(ticker="PLD", name="Prologis", sector=Sector.REIT_INDUSTRIAL),
        Company(ticker="AMZN", name="Amazon", sector=Sector.ECOMMERCE),
    ]
    count = storage.upsert_companies(companies)
    assert count == 2
    assert storage.get_active_tickers() == ["PLD", "AMZN"]


# ---------------------------------------------------------------------------
# Integration test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_pipeline_integration(provider, storage):
    """End-to-end: fetch → parse → chunk → store → verify."""
    from warehouse_signal.ingestion.pipeline import ingest_transcript

    result = await ingest_transcript(provider, storage, "AMZN", 2024, 4)
    assert result is not None
    assert result.quarter_key == "AMZN_2024Q4"

    # Should skip on second call (already stored)
    result2 = await ingest_transcript(provider, storage, "AMZN", 2024, 4)
    assert result2 is None

    # Force re-fetch
    result3 = await ingest_transcript(
        provider, storage, "AMZN", 2024, 4, force=True
    )
    assert result3 is not None

"""Abstract interface for transcript providers.

Every provider (FMP, EarningsCall, Finnhub, etc.) implements this interface.
The rest of the system only talks to TranscriptProvider, never to a concrete
provider directly. This lets you swap providers with a single env var change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from warehouse_signal.models.schemas import (
    EarningsEvent,
    Transcript,
    TranscriptMetadata,
)


class TranscriptProvider(ABC):
    """Abstract interface that all transcript sources must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier for this provider (e.g. 'fmp', 'earningscall')."""
        ...

    # ------------------------------------------------------------------
    # Transcript retrieval
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_transcript(self, ticker: str, year: int, quarter: int) -> Transcript | None:
        """Fetch a single transcript by ticker, year, and quarter.

        Returns None if the transcript is not available (e.g. the call
        hasn't happened yet, or the provider doesn't cover this company).
        """
        ...

    @abstractmethod
    async def list_available_transcripts(self, ticker: str) -> list[TranscriptMetadata]:
        """List all available transcript dates for a given ticker.

        Returns metadata only (no full text). Used to discover which
        quarters are available for backfill.
        """
        ...

    # ------------------------------------------------------------------
    # Calendar / scheduling
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_earnings_calendar(
        self,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[EarningsEvent]:
        """Fetch upcoming/recent earnings events.

        Used by the scheduler to know when to poll for new transcripts.
        Date format: YYYY-MM-DD.
        """
        ...

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Clean up any resources (HTTP clients, etc.)."""
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

"""Abstract interface for signal analyzers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from warehouse_signal.models.schemas import ChunkExtraction, TranscriptChunk


class SignalAnalyzer(ABC):
    """Abstract interface that all signal extraction backends must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier for this analyzer (e.g. 'claude', 'mock')."""
        ...

    @abstractmethod
    async def extract_signals(
        self,
        chunk: TranscriptChunk,
        ticker: str,
        company_name: str,
        year: int,
        quarter: int,
    ) -> ChunkExtraction:
        """Analyze a single transcript chunk for warehouse expansion signals."""
        ...

    async def close(self) -> None:
        """Clean up any resources."""
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

"""EarningsCall.biz transcript provider.

API docs: https://earningscall.biz/api-guide
Key advantage: pre-segmented prepared remarks vs Q&A, speaker identification.
"""

from __future__ import annotations

from datetime import date, datetime

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from warehouse_signal.config import Config
from warehouse_signal.models.schemas import (
    CallTiming,
    EarningsEvent,
    SectionType,
    Transcript,
    TranscriptMetadata,
    TranscriptSection,
)
from warehouse_signal.providers.base import TranscriptProvider

BASE_URL = "https://v2.api.earningscall.biz/api"


class EarningsCallProvider(TranscriptProvider):
    """Transcript provider backed by EarningsCall.biz API."""

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or Config.EARNINGSCALL_API_KEY
        if not self._api_key:
            raise ValueError(
                "EARNINGSCALL_API_KEY is required. Set it in .env or pass to constructor."
            )
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=30.0,
            headers={
                "Accept": "application/json",
                "X-Api-Key": self._api_key,
            },
        )

    @property
    def name(self) -> str:
        return "earningscall"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=3, max=15))
    async def _get(self, path: str, params: dict | None = None) -> dict | list | None:
        resp = await self._client.get(path, params=params or {})
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and data.get("error"):
            return None
        return data

    async def get_transcript(self, ticker: str, year: int, quarter: int) -> Transcript | None:
        # EarningsCall provides separate endpoints for basic and segmented transcripts.
        # Try the segmented (Q&A split) endpoint first, fall back to basic.
        data = await self._get(
            f"/transcript",
            params={"symbol": ticker.upper(), "year": year, "quarter": quarter},
        )
        if not data:
            return None

        # Handle both response shapes
        raw_text = ""
        sections: list[TranscriptSection] = []

        if isinstance(data, dict):
            prepared = data.get("preparedRemarks", "")
            qa = data.get("questionsAndAnswers", "")
            raw_text = data.get("text", "") or f"{prepared}\n\n{qa}"

            if prepared:
                sections.append(
                    TranscriptSection(section_type=SectionType.PREPARED_REMARKS, text=prepared)
                )
            if qa:
                sections.append(
                    TranscriptSection(section_type=SectionType.QA, text=qa)
                )

            if not sections and raw_text:
                sections.append(
                    TranscriptSection(section_type=SectionType.FULL, text=raw_text)
                )

        if not raw_text:
            return None

        call_date_str = data.get("date") or data.get("conferenceDate", "")
        call_date = None
        if call_date_str:
            try:
                call_date = datetime.fromisoformat(
                    call_date_str.replace("Z", "+00:00")
                ).date()
            except (ValueError, TypeError):
                pass

        metadata = TranscriptMetadata(
            ticker=ticker.upper(),
            year=year,
            quarter=quarter,
            call_date=call_date,
            provider=self.name,
        )

        return Transcript(
            metadata=metadata,
            raw_text=raw_text,
            sections=sections,
        )

    async def list_available_transcripts(self, ticker: str) -> list[TranscriptMetadata]:
        data = await self._get(f"/events", params={"symbol": ticker.upper()})
        if not data or not isinstance(data, list):
            return []

        results = []
        for record in data:
            results.append(
                TranscriptMetadata(
                    ticker=ticker.upper(),
                    year=int(record.get("year", 0)),
                    quarter=int(record.get("quarter", 0)),
                    provider=self.name,
                )
            )
        return results

    async def get_earnings_calendar(
        self,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[EarningsEvent]:
        params = {}
        if from_date:
            params["date"] = from_date  # EarningsCall uses single date for calendar

        data = await self._get("/calendar", params=params)
        if not data or not isinstance(data, list):
            return []

        events = []
        for record in data:
            try:
                event_date = date.fromisoformat(record.get("date", "")[:10])
            except (ValueError, TypeError):
                continue

            events.append(
                EarningsEvent(
                    ticker=record.get("symbol", record.get("ticker", "")),
                    company_name=record.get("companyName", record.get("company_name")),
                    call_date=event_date,
                    fiscal_year=record.get("year"),
                    fiscal_quarter=record.get("quarter"),
                    transcript_available=record.get("transcriptReady", False),
                )
            )
        return events

    async def close(self) -> None:
        await self._client.aclose()

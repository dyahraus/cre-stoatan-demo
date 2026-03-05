"""Financial Modeling Prep transcript provider.

API docs: https://site.financialmodelingprep.com/developer/docs
Endpoints used (stable API):
  - GET /stable/earning-call-transcript?symbol={s}&quarter={q}&year={y}&apikey={key}
  - GET /stable/earning-call-transcript?symbol={s}&apikey={key}  (all transcripts)
  - GET /stable/earnings-calendar?from={date}&to={date}&apikey={key}
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

BASE_URL = "https://financialmodelingprep.com"


class FMPProvider(TranscriptProvider):
    """Transcript provider backed by Financial Modeling Prep API."""

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or Config.FMP_API_KEY
        if not self._api_key:
            raise ValueError("FMP_API_KEY is required. Set it in .env or pass to constructor.")
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=30.0,
            headers={"Accept": "application/json"},
        )

    @property
    def name(self) -> str:
        return "fmp"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    async def _get(self, path: str, params: dict | None = None) -> list | dict | None:
        params = params or {}
        params["apikey"] = self._api_key
        resp = await self._client.get(path, params=params)
        # Return None for client errors (no transcript found, bad params, etc.)
        if 400 <= resp.status_code < 500:
            return None
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, str):
            return None
        if isinstance(data, dict) and "Error Message" in data:
            return None
        return data

    # ------------------------------------------------------------------
    # TranscriptProvider interface
    # ------------------------------------------------------------------

    async def get_transcript(self, ticker: str, year: int, quarter: int) -> Transcript | None:
        data = await self._get(
            "/stable/earning-call-transcript",
            params={"symbol": ticker.upper(), "quarter": quarter, "year": year},
        )
        if not data or (isinstance(data, list) and len(data) == 0):
            return None

        # Stable API returns a list with one item
        record = data[0] if isinstance(data, list) else data
        raw_text = record.get("content", "")
        if not raw_text:
            return None

        call_date_str = record.get("date", "")
        call_date = None
        if call_date_str:
            try:
                call_date = datetime.fromisoformat(call_date_str.replace("Z", "+00:00")).date()
            except (ValueError, TypeError):
                pass

        metadata = TranscriptMetadata(
            ticker=ticker.upper(),
            year=year,
            quarter=quarter,
            call_date=call_date,
            provider=self.name,
        )

        # FMP returns a single content blob — section parsing happens downstream
        sections = [
            TranscriptSection(
                section_type=SectionType.FULL,
                text=raw_text,
            )
        ]

        return Transcript(
            metadata=metadata,
            raw_text=raw_text,
            sections=sections,
        )

    async def list_available_transcripts(
        self, ticker: str, start_year: int = 2020, end_year: int | None = None,
    ) -> list[TranscriptMetadata]:
        """List available transcripts by probing each quarter.

        The stable API requires both year and quarter, so we probe each
        quarter from start_year to end_year (default: current year).
        """
        if end_year is None:
            end_year = datetime.now().year

        results: list[TranscriptMetadata] = []
        for year in range(end_year, start_year - 1, -1):
            for quarter in range(4, 0, -1):
                data = await self._get(
                    "/stable/earning-call-transcript",
                    params={"symbol": ticker.upper(), "year": year, "quarter": quarter},
                )
                if data and isinstance(data, list) and len(data) > 0:
                    record = data[0]
                    call_date_str = record.get("date", "")
                    call_date = None
                    if call_date_str:
                        try:
                            call_date = datetime.fromisoformat(
                                call_date_str.replace("Z", "+00:00")
                            ).date()
                        except (ValueError, TypeError):
                            pass
                    results.append(
                        TranscriptMetadata(
                            ticker=ticker.upper(),
                            year=year,
                            quarter=quarter,
                            call_date=call_date,
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
            params["from"] = from_date
        if to_date:
            params["to"] = to_date

        data = await self._get("/stable/earnings-calendar", params=params)
        if not data or not isinstance(data, list):
            return []

        events = []
        for record in data:
            try:
                event_date = date.fromisoformat(record.get("date", ""))
            except (ValueError, TypeError):
                continue

            timing = CallTiming.UNKNOWN
            time_str = record.get("time", "")
            if time_str == "bmo":
                timing = CallTiming.BEFORE_MARKET
            elif time_str == "amc":
                timing = CallTiming.AFTER_MARKET

            events.append(
                EarningsEvent(
                    ticker=record.get("symbol", ""),
                    call_date=event_date,
                    call_timing=timing,
                    fiscal_year=record.get("fiscalDateEnding", "")[:4] if record.get("fiscalDateEnding") else None,
                    fiscal_quarter=None,  # FMP calendar doesn't always include quarter
                )
            )
        return events

    async def close(self) -> None:
        await self._client.aclose()

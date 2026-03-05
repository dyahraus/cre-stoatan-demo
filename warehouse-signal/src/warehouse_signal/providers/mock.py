"""Mock transcript provider for local development and testing.

Returns synthetic transcripts with warehouse-relevant language so you can
develop the full pipeline without needing a paid API key.
"""

from __future__ import annotations

from datetime import date

from warehouse_signal.models.schemas import (
    CallTiming,
    EarningsEvent,
    SectionType,
    Transcript,
    TranscriptMetadata,
    TranscriptSection,
)
from warehouse_signal.providers.base import TranscriptProvider

# ---------------------------------------------------------------------------
# Synthetic transcript templates with varying warehouse signal strength
# ---------------------------------------------------------------------------

_HIGH_SIGNAL = """
Thank you, operator. Good morning, everyone. I want to start by discussing our
distribution network strategy. As we communicated last quarter, we are actively
expanding our logistics footprint. We broke ground on two new distribution centers
this quarter — one in the Indianapolis market and one in the Inland Empire.

Our supply chain team has identified capacity constraints in our Midwest hub network.
Current utilization across our DCs is running at 94%, which is above our target of 85%.
To address this, we've committed approximately $180 million in logistics capex for the
next 18 months, focused on adding 2.4 million square feet of new warehouse capacity.

We're also seeing strong demand from our e-commerce channel. Direct-to-consumer fulfillment
now represents 38% of our total shipments, up from 29% a year ago. This shift requires
shorter last-mile delivery windows, which is driving our decision to add regional
fulfillment nodes in secondary markets.

Looking at our real estate pipeline, we have three build-to-suit projects under letter
of intent — two in the Southeast and one in the Dallas-Fort Worth corridor. We expect
these to be operational by Q3 of next year.

On the automation front, we're investing in goods-to-person robotics across our top
five DCs. This doesn't reduce our footprint needs — it increases throughput per square
foot, but the volume growth more than offsets that efficiency gain.
"""

_LOW_SIGNAL = """
Thank you, operator. Good morning, everyone. Let me walk through our quarterly results.

Revenue came in at $4.2 billion, up 6% year over year. Gross margin expanded 40 basis
points to 34.2%, driven by favorable product mix and pricing actions we implemented
in Q2. Operating expenses were well controlled at 22.1% of revenue.

Our working capital position remains strong. Inventory days improved by 3 days
sequentially to 47 days, reflecting better demand planning and our ongoing SKU
rationalization initiative.

We returned $350 million to shareholders this quarter through dividends and share
repurchases. Our balance sheet remains healthy with net debt to EBITDA at 1.8x.

Looking ahead, we're maintaining our full-year guidance of $17.5 to $18.0 billion
in revenue and adjusted EPS of $8.40 to $8.60.

Operator, let's open the line for questions.
"""

_MODERATE_SIGNAL = """
Thank you, operator. Good morning. Let me discuss our operational highlights.

Revenue grew 8% year over year to $6.1 billion. We saw particular strength in our
industrial segment, which was up 12%.

On the supply chain side, we continue to evaluate our network configuration. Our
current distribution footprint of 28 facilities serving the continental US is adequate
for today's volume, but we're conducting a network study to assess whether nearshoring
trends will require us to add capacity in the next 2-3 years. No commitments yet, but
our real estate team is actively monitoring options in the Midwest and Southeast corridors.

Transportation costs remain elevated. We've partially offset this through route
optimization, but we believe the structural solution is getting product closer to the
end customer, which may involve additional warehouse investments down the road.

Our inventory repositioning program is on track. We've shifted approximately $200 million
of inventory from our West Coast DCs to interior locations to improve service levels
and reduce transportation costs.

We remain disciplined on capital allocation and will communicate any network expansion
plans once they're finalized.
"""

_MOCK_TRANSCRIPTS: dict[str, str] = {
    "high": _HIGH_SIGNAL.strip(),
    "moderate": _MODERATE_SIGNAL.strip(),
    "low": _LOW_SIGNAL.strip(),
}

_TICKER_SIGNAL_MAP: dict[str, str] = {
    # High-signal industrial companies
    "PLD": "high", "STAG": "high", "REXR": "high", "XPO": "high",
    "AMZN": "high", "WMT": "high", "FDX": "high", "UPS": "high",
    # Moderate
    "HD": "moderate", "LOW": "moderate", "TGT": "moderate", "COST": "moderate",
    "KR": "moderate", "SYY": "moderate",
}


class MockProvider(TranscriptProvider):
    """Returns synthetic transcripts for development and testing."""

    @property
    def name(self) -> str:
        return "mock"

    async def get_transcript(self, ticker: str, year: int, quarter: int) -> Transcript | None:
        signal_level = _TICKER_SIGNAL_MAP.get(ticker.upper(), "low")
        raw_text = _MOCK_TRANSCRIPTS[signal_level]

        metadata = TranscriptMetadata(
            ticker=ticker.upper(),
            year=year,
            quarter=quarter,
            call_date=date(year, quarter * 3, 15),  # approximate
            call_timing=CallTiming.BEFORE_MARKET,
            provider=self.name,
        )

        sections = [
            TranscriptSection(
                section_type=SectionType.PREPARED_REMARKS,
                speaker="CEO",
                speaker_role="CEO",
                text=raw_text,
            )
        ]

        return Transcript(
            metadata=metadata,
            raw_text=raw_text,
            sections=sections,
        )

    async def list_available_transcripts(self, ticker: str) -> list[TranscriptMetadata]:
        # Simulate 4 years of quarterly data
        results = []
        for year in range(2021, 2025):
            for q in range(1, 5):
                results.append(
                    TranscriptMetadata(
                        ticker=ticker.upper(),
                        year=year,
                        quarter=q,
                        provider=self.name,
                    )
                )
        return results

    async def get_earnings_calendar(
        self,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[EarningsEvent]:
        # Return a few mock upcoming events
        return [
            EarningsEvent(
                ticker="PLD",
                company_name="Prologis Inc",
                call_date=date(2025, 4, 15),
                call_timing=CallTiming.BEFORE_MARKET,
                fiscal_year=2025,
                fiscal_quarter=1,
                transcript_available=True,
            ),
            EarningsEvent(
                ticker="AMZN",
                company_name="Amazon.com Inc",
                call_date=date(2025, 4, 25),
                call_timing=CallTiming.AFTER_MARKET,
                fiscal_year=2025,
                fiscal_quarter=1,
                transcript_available=False,
            ),
        ]

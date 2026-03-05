"""Core data models for the warehouse signal system."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SectionType(str, Enum):
    PREPARED_REMARKS = "prepared_remarks"
    QA = "qa"
    FULL = "full"  # unsegmented


class CallTiming(str, Enum):
    BEFORE_MARKET = "before_market"
    DURING_MARKET = "during_market"
    AFTER_MARKET = "after_market"
    UNKNOWN = "unknown"


class Sector(str, Enum):
    """Coarse sector labels relevant to warehouse demand."""
    REIT_INDUSTRIAL = "reit_industrial"
    REIT_DIVERSIFIED = "reit_diversified"
    LOGISTICS_3PL = "logistics_3pl"
    ECOMMERCE = "ecommerce"
    RETAIL = "retail"
    MANUFACTURING = "manufacturing"
    FOOD_DISTRIBUTION = "food_distribution"
    AUTOMOTIVE = "automotive"
    CONSTRUCTION = "construction"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Company
# ---------------------------------------------------------------------------

class Company(BaseModel):
    """A public company in our tracking universe."""
    ticker: str
    name: str
    sector: Sector = Sector.OTHER
    cik: Optional[str] = None
    sp500: bool = True
    # Which geographic markets does this company have warehouse/logistics exposure to?
    # Populated later via LLM extraction or manual mapping.
    geo_exposure: list[str] = Field(default_factory=list)
    active: bool = True


# ---------------------------------------------------------------------------
# Transcript
# ---------------------------------------------------------------------------

class TranscriptMetadata(BaseModel):
    """Metadata returned by a transcript provider."""
    ticker: str
    year: int
    quarter: int
    call_date: Optional[date] = None
    call_timing: CallTiming = CallTiming.UNKNOWN
    provider: str  # e.g. "fmp", "earningscall"


class TranscriptSection(BaseModel):
    """A section of a transcript (prepared remarks or Q&A)."""
    section_type: SectionType
    speaker: Optional[str] = None
    speaker_role: Optional[str] = None  # e.g. "CEO", "CFO", "Analyst"
    text: str


class Transcript(BaseModel):
    """A full earnings call transcript with metadata and parsed sections."""
    metadata: TranscriptMetadata
    raw_text: str
    sections: list[TranscriptSection] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def quarter_key(self) -> str:
        """Canonical key like 'AAPL_2024Q3'."""
        return f"{self.metadata.ticker}_{self.metadata.year}Q{self.metadata.quarter}"

    @property
    def has_sections(self) -> bool:
        return len(self.sections) > 0 and any(
            s.section_type != SectionType.FULL for s in self.sections
        )


# ---------------------------------------------------------------------------
# Calendar / Scheduling
# ---------------------------------------------------------------------------

class EarningsEvent(BaseModel):
    """An upcoming or recent earnings call event."""
    ticker: str
    company_name: Optional[str] = None
    call_date: date
    call_timing: CallTiming = CallTiming.UNKNOWN
    fiscal_year: Optional[int] = None
    fiscal_quarter: Optional[int] = None
    transcript_available: bool = False


# ---------------------------------------------------------------------------
# Chunk (for LLM analysis)
# ---------------------------------------------------------------------------

class TranscriptChunk(BaseModel):
    """A chunk of transcript text sized for LLM processing."""
    chunk_id: str
    transcript_key: str  # e.g. "AAPL_2024Q3"
    chunk_index: int
    text: str
    section_type: SectionType
    speaker: Optional[str] = None
    speaker_role: Optional[str] = None
    token_estimate: int = 0


# ---------------------------------------------------------------------------
# Signal Extraction
# ---------------------------------------------------------------------------

class MoveType(str, Enum):
    """Type of warehouse/logistics move signaled."""
    EXPANSION = "expansion"
    CONSOLIDATION = "consolidation"
    RELOCATION = "relocation"
    OPTIMIZATION = "optimization"
    NO_CHANGE = "no_change"
    UNKNOWN = "unknown"


class TimeHorizon(str, Enum):
    """Temporal orientation of the signal."""
    IMMEDIATE = "immediate"
    NEAR_TERM = "near_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"
    HISTORICAL = "historical"
    UNSPECIFIED = "unspecified"


class SentimentDirection(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class GeographicMention(BaseModel):
    """A geographic area mentioned in context of warehouse/logistics."""
    region: str
    confidence: float = Field(ge=0.0, le=1.0)
    context: str = ""


class Sentiment(BaseModel):
    polarity: float = Field(ge=-1.0, le=1.0, default=0.0)
    intensity: str = "low"
    direction: SentimentDirection = SentimentDirection.NEUTRAL


class SignalFlags(BaseModel):
    """Structured binary/categorical signal flags."""
    capex_expansion: bool = False
    demand_strength: str = "stable"
    vacancy_mention: bool = False
    rent_pressure: str = "neutral"
    construction_pipeline: str = "none"
    automation_investment: bool = False
    network_redesign: bool = False
    build_to_suit: bool = False
    last_mile_expansion: bool = False


class ChunkExtraction(BaseModel):
    """Full structured extraction from a single transcript chunk."""
    warehouse_relevance: float = Field(ge=0.0, le=1.0)
    expansion_score: float = Field(ge=0.0, le=1.0)
    move_type: MoveType = MoveType.UNKNOWN
    time_horizon: TimeHorizon = TimeHorizon.UNSPECIFIED
    sentiment: Sentiment = Field(default_factory=Sentiment)
    geographic_mentions: list[GeographicMention] = Field(default_factory=list)
    signals: SignalFlags = Field(default_factory=SignalFlags)
    evidence_quote: str = ""
    reasoning: str = ""


# ---------------------------------------------------------------------------
# Company Score
# ---------------------------------------------------------------------------

class CompanyScore(BaseModel):
    """Aggregated company-level expansion score."""
    ticker: str
    company_name: str
    sector: Sector = Sector.OTHER
    composite_score: float = Field(ge=0.0, le=1.0)
    avg_warehouse_relevance: float = 0.0
    avg_expansion_score: float = 0.0
    max_expansion_score: float = 0.0
    num_relevant_chunks: int = 0
    total_chunks: int = 0
    top_geographies: list[str] = Field(default_factory=list)
    dominant_time_horizon: TimeHorizon = TimeHorizon.UNSPECIFIED
    dominant_move_type: MoveType = MoveType.UNKNOWN
    has_capex_signal: bool = False
    has_build_to_suit: bool = False
    has_last_mile: bool = False
    evidence_snippets: list[str] = Field(default_factory=list)
    transcript_keys: list[str] = Field(default_factory=list)
    scored_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

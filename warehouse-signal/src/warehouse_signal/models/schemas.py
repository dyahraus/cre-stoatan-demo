"""Core data models for the warehouse signal system."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Optional

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


class SignalTier(str, Enum):
    """Plain-English tier shown to users instead of a bare 0..1 number."""
    STRONG = "strong"
    MODERATE = "moderate"
    WATCHLIST = "watchlist"
    NOISE = "noise"


class KeywordCategory(str, Enum):
    """Top-level keyword grouping in a signal framework."""
    INDUSTRIAL_TRANSFORMATION = "industrial_transformation"
    SUPPLY_CHAIN = "supply_chain"
    COMMITMENT_LEVEL = "commitment_level"


class ConceptMode(str, Enum):
    """How a SignalConcept matches: vector embeddings or LLM judgment."""
    EMBEDDING = "embedding"
    LLM = "llm"


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
# Score components (used by both CompanyScore and TranscriptScore)
# ---------------------------------------------------------------------------

class ScoreComponents(BaseModel):
    """Weighted breakdown of a composite score so the user can see how it's built."""
    max_expansion: float = 0.0
    weighted_avg: float = 0.0
    flag_bonus: float = 0.0
    time_bonus: float = 0.0
    keyword_component: float = 0.0
    commitment_component: float = 0.0
    concept_component: float = 0.0
    boost_multiplier: float = 1.0


class BoostConfig(BaseModel):
    """Per-framework section + speaker-role boost multipliers.

    Each multiplier is in [0.5, 1.5]. Lookups are case-insensitive
    prefix matches on the speaker_role string ("Chief Executive Officer"
    still hits "CEO"). Defaults to 1.0 everywhere == no bias.
    """
    prepared_remarks: float = Field(default=1.0, ge=0.5, le=1.5)
    qa: float = Field(default=1.0, ge=0.5, le=1.5)
    full: float = Field(default=1.0, ge=0.5, le=1.5)
    speaker_role: dict[str, float] = Field(default_factory=dict)


class ChunkContribution(BaseModel):
    """One chunk's contribution to a composite score."""
    chunk_id: str
    chunk_index: int
    section_type: SectionType = SectionType.FULL
    contribution: float = 0.0
    expansion_score: float = 0.0
    warehouse_relevance: float = 0.0
    keyword_hit_count: int = 0
    evidence_quote: str = ""
    reasoning: str = ""


class ExtractedMetrics(BaseModel):
    """Concrete numbers brokers care about, summed/aggregated across chunks."""
    capex_amount_usd: Optional[int] = None
    square_footage_sqft: Optional[int] = None
    facility_count: Optional[int] = None
    target_completion: Optional[str] = None


# ---------------------------------------------------------------------------
# Company Score
# ---------------------------------------------------------------------------

class CompanyScore(BaseModel):
    """Aggregated company-level expansion score."""
    ticker: str
    company_name: str
    sector: Sector = Sector.OTHER
    composite_score: float = Field(ge=0.0, le=1.0)
    tier: SignalTier = SignalTier.NOISE
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
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
    score_components: Optional[ScoreComponents] = None
    top_contributions: list[ChunkContribution] = Field(default_factory=list)
    scored_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Signal Framework (configurable keyword library)
# ---------------------------------------------------------------------------

class SignalKeyword(BaseModel):
    """A single keyword/phrase rule within a framework."""
    id: str
    framework_id: str
    category: KeywordCategory
    phrase: str
    is_regex: bool = False
    weight: float = Field(ge=1.0, le=10.0, default=5.0)
    # Optional regex that must match within COMPANION_WINDOW tokens of the phrase.
    # Used for commitment keywords that require a $ amount, sqft, or specific date.
    companion_pattern: Optional[str] = None
    notes: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SignalConcept(BaseModel):
    """A semantic concept — matched against chunk embeddings.

    Tolerant of paraphrase: a chunk that says "we lack the storage
    capacity to support continued growth" can fire on the concept
    "warehouse capacity constraints" without literal phrase overlap.
    """
    id: str
    framework_id: str
    category: KeywordCategory
    label: str
    description: str = ""
    example_phrases: list[str] = Field(default_factory=list)
    weight: float = Field(ge=1.0, le=10.0, default=5.0)
    threshold: float = Field(ge=0.5, le=0.9, default=0.65)
    mode: ConceptMode = ConceptMode.EMBEDDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConceptHit(BaseModel):
    """A single semantic match of a SignalConcept against a chunk."""
    concept_id: str
    chunk_id: str
    transcript_key: str
    category: KeywordCategory
    label: str
    similarity: float
    weight_contribution: float
    mode_used: ConceptMode = ConceptMode.EMBEDDING


class SignalFramework(BaseModel):
    """A named bundle of keywords and weights."""
    id: str
    name: str
    description: str = ""
    is_default: bool = False
    keywords: list[SignalKeyword] = Field(default_factory=list)
    concepts: list[SignalConcept] = Field(default_factory=list)
    boosts: BoostConfig = Field(default_factory=BoostConfig)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class KeywordHit(BaseModel):
    """A single literal match of a SignalKeyword against a chunk."""
    keyword_id: str
    chunk_id: str
    transcript_key: str
    category: KeywordCategory
    phrase: str
    match_text: str
    match_offset: int
    weight_contribution: float


# ---------------------------------------------------------------------------
# Per-transcript score
# ---------------------------------------------------------------------------

class TranscriptScore(BaseModel):
    """First-class per-transcript score record."""
    quarter_key: str
    ticker: str
    year: int
    quarter: int
    framework_id: str
    composite_score: float = Field(ge=0.0, le=1.0, default=0.0)
    tier: SignalTier = SignalTier.NOISE
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    score_components: ScoreComponents = Field(default_factory=ScoreComponents)
    top_contributions: list[ChunkContribution] = Field(default_factory=list)
    keyword_hit_summary: dict[str, int] = Field(default_factory=dict)
    extracted_metrics: ExtractedMetrics = Field(default_factory=ExtractedMetrics)
    num_relevant_chunks: int = 0
    total_chunks: int = 0
    scored_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Watchlists & Scan Jobs (Phase 3)
# ---------------------------------------------------------------------------

class Watchlist(BaseModel):
    id: str
    name: str
    tickers: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ScanJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class ScanJob(BaseModel):
    id: str
    status: ScanJobStatus = ScanJobStatus.PENDING
    params: dict[str, Any] = Field(default_factory=dict)
    progress: dict[str, Any] = Field(default_factory=dict)
    results_summary: dict[str, Any] = Field(default_factory=dict)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

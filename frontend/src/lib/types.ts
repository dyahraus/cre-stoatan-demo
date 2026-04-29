export type Sector =
  | "reit_industrial"
  | "reit_diversified"
  | "logistics_3pl"
  | "ecommerce"
  | "retail"
  | "grocery"
  | "industrial_mfg"
  | "cold_chain"
  | "automotive"
  | "healthcare_pharma"
  | "building_materials"
  | "data_center"
  | "other";

export type MoveType =
  | "expansion"
  | "consolidation"
  | "relocation"
  | "new_market_entry"
  | "optimization"
  | "unknown";

export type TimeHorizon =
  | "immediate"
  | "near_term"
  | "medium_term"
  | "long_term"
  | "unspecified";

export interface CompanyScore {
  ticker: string;
  company_name: string;
  sector: Sector;
  composite_score: number;
  tier: SignalTier;
  confidence: number;
  avg_warehouse_relevance: number;
  avg_expansion_score: number;
  max_expansion_score: number;
  num_relevant_chunks: number;
  total_chunks: number;
  top_geographies: string[];
  dominant_time_horizon: TimeHorizon;
  dominant_move_type: MoveType;
  has_capex_signal: boolean;
  has_build_to_suit: boolean;
  has_last_mile: boolean;
  evidence_snippets: string[];
  transcript_keys: string[];
  score_components?: ScoreComponents | null;
  top_contributions?: ChunkContribution[];
  scored_at?: string;
}

export interface SignalExtraction {
  chunk_id: string;
  transcript_key: string;
  extraction_model: string;
  extraction_version: string;
  warehouse_relevance: number;
  expansion_score: number;
  move_type: MoveType;
  time_horizon: TimeHorizon;
  geographic_mentions: { region: string; context: string }[];
  signals_json: {
    signals?: {
      capex_mention: boolean;
      build_to_suit: boolean;
      last_mile: boolean;
      lease_expansion: boolean;
      new_facility: boolean;
      automation_investment: boolean;
    };
    sentiment?: {
      direction: string;
      confidence: number;
    };
  };
  evidence_quote: string;
  reasoning: string;
  extracted_at: string;
}

export interface GeographySummary {
  region: string;
  num_companies: number;
  avg_score: number;
  max_score: number;
  tickers: string[];
}

export interface Stats {
  companies: number;
  transcripts: number;
  transcripts_unprocessed: number;
  chunks: number;
  signal_extractions: number;
  company_scores: number;
}

export interface EnumValues {
  sectors: string[];
  move_types: string[];
  time_horizons: string[];
  tiers: SignalTier[];
  tier_bounds: { tier: SignalTier; min_score: number; description: string }[];
}

export type SignalTier = "strong" | "moderate" | "watchlist" | "noise";

export type KeywordCategory =
  | "industrial_transformation"
  | "supply_chain"
  | "commitment_level";

export interface SignalKeyword {
  id: string;
  framework_id: string;
  category: KeywordCategory;
  phrase: string;
  is_regex: boolean;
  weight: number;
  companion_pattern: string | null;
  notes: string;
  created_at: string;
}

export interface SignalFramework {
  id: string;
  name: string;
  description: string;
  is_default: boolean;
  keywords: SignalKeyword[];
  boosts?: BoostConfig;
  created_at: string;
  updated_at: string;
}

export interface KeywordHit {
  keyword_id: string;
  chunk_id: string;
  transcript_key: string;
  category: KeywordCategory;
  phrase: string;
  match_text: string;
  match_offset: number;
  weight_contribution: number;
}

export interface DryRunResult {
  framework_id: string;
  hits: KeywordHit[];
  keyword_score: number;
  commitment_score: number;
  hybrid_chunk_score: number;
  llm_expansion_score: number;
  summary: Record<string, number>;
  total_hits: number;
}

export interface ScoreComponents {
  max_expansion: number;
  weighted_avg: number;
  flag_bonus: number;
  time_bonus: number;
  keyword_component: number;
  commitment_component: number;
  boost_multiplier?: number;
}

export interface BoostConfig {
  prepared_remarks: number;
  qa: number;
  full: number;
  speaker_role: Record<string, number>;
}

export interface ChunkContribution {
  chunk_id: string;
  chunk_index: number;
  section_type: string;
  contribution: number;
  expansion_score: number;
  warehouse_relevance: number;
  keyword_hit_count: number;
  evidence_quote: string;
  reasoning: string;
}

export interface ExtractedMetrics {
  capex_amount_usd: number | null;
  square_footage_sqft: number | null;
  facility_count: number | null;
  target_completion: string | null;
}

export interface TranscriptScore {
  quarter_key: string;
  ticker: string;
  year: number;
  quarter: number;
  framework_id: string;
  composite_score: number;
  tier: SignalTier;
  confidence: number;
  score_components: ScoreComponents;
  top_contributions: ChunkContribution[];
  keyword_hit_summary: Record<string, number>;
  extracted_metrics: ExtractedMetrics;
  num_relevant_chunks: number;
  total_chunks: number;
  scored_at: string;
}

export interface CompanyHistoryEntry {
  quarter_key: string;
  year: number;
  quarter: number;
  framework_id: string;
  composite_score: number;
  tier: SignalTier;
  confidence: number;
  scored_at: string;
  extracted_metrics: ExtractedMetrics;
  top_evidence: string;
}

export interface UploadResponse {
  quarter_key: string;
  ticker: string;
  year: number;
  quarter: number;
  raw_text_length: number;
  chunk_count: number;
  sections_detected: boolean;
}

export interface Watchlist {
  id: string;
  name: string;
  tickers: string[];
  created_at: string;
  updated_at: string;
}

export interface ScanJob {
  id: string;
  status: "pending" | "running" | "completed" | "failed" | "canceled";
  params: {
    mode: string;
    tickers: string[];
    year: number;
    quarter: number;
    framework_id: string;
  };
  progress: {
    completed?: number;
    total?: number;
    events?: ScanProgressEvent[];
  };
  results_summary: {
    scored?: { ticker: string; quarter_key: string; composite: number; tier: SignalTier }[];
    skipped?: { ticker: string; reason: string }[];
  };
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  created_at: string;
}

export type ScanProgressEvent =
  | { type: "started"; total: number }
  | { type: "progress"; ticker: string; phase: string; index?: number }
  | { type: "scored"; ticker: string; quarter_key: string; composite: number; tier: SignalTier; ingested: boolean }
  | { type: "skip"; ticker: string; reason: string }
  | { type: "warn"; ticker: string; message: string }
  | { type: "error"; message: string }
  | { type: "done"; scored?: number; skipped?: number; status?: string };

// Demo pipeline types

export interface DemoTranscript {
  ticker: string;
  company_name: string;
  year: number;
  quarter: number;
  quarter_key: string;
  raw_text_length: number;
  call_date: string | null;
}

export interface DemoSection {
  section_type: string;
  text_length: number;
  text_preview: string;
}

export interface DemoParseResult {
  sections: DemoSection[];
  boundary_found: boolean;
}

export interface DemoChunk {
  chunk_index: number;
  chunk_id: string;
  section_type: string;
  token_estimate: number;
  text_preview: string;
  text: string;
}

export interface DemoChunkResult {
  chunks: DemoChunk[];
  total_chunks: number;
  avg_tokens: number;
}

export interface DemoScoreComponent {
  weight: number;
  value: number;
  contribution: number;
  flags?: { capex: boolean; build_to_suit: boolean; last_mile: boolean };
  time_horizon?: string;
}

export interface DemoScoreResult {
  composite_score: number;
  is_relevant: boolean;
  components: {
    max_expansion: DemoScoreComponent;
    weighted_avg: DemoScoreComponent;
    flag_bonus: DemoScoreComponent;
    time_bonus: DemoScoreComponent;
  };
  extraction_summary: {
    warehouse_relevance: number;
    expansion_score: number;
    move_type: string;
    time_horizon: string;
    evidence_quote: string;
  };
  note: string;
}

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
}

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

"""Extraction prompt templates for warehouse signal analysis."""

SYSTEM_PROMPT = """You are a commercial real estate analyst specializing in industrial/warehouse properties. Your job is to analyze earnings call transcript excerpts and identify signals related to warehouse, distribution center, and logistics facility expansion, consolidation, or relocation.

You are evaluating text from a {section_type} section of a {ticker} ({company_name}) earnings call for {year}Q{quarter}.

Respond ONLY with a JSON object matching the exact schema below. No markdown, no explanation outside the JSON."""

EXTRACTION_PROMPT = """Analyze this earnings call excerpt for warehouse and logistics real estate signals.

<transcript_chunk>
{chunk_text}
</transcript_chunk>

Return a JSON object with exactly these fields:

{{
  "warehouse_relevance": <float 0.0-1.0, how relevant is this text to warehouse/distribution center/logistics real estate>,
  "expansion_score": <float 0.0-1.0, strength of warehouse expansion signal. 0=no signal, 0.3=vague hints, 0.6=clear discussion, 0.9=committed plans with specifics>,
  "move_type": <"expansion"|"consolidation"|"relocation"|"optimization"|"no_change"|"unknown">,
  "time_horizon": <"immediate"|"near_term"|"medium_term"|"long_term"|"historical"|"unspecified">,
  "sentiment": {{
    "polarity": <float -1.0 to 1.0, negative=bearish on space needs, positive=bullish>,
    "intensity": <"low"|"moderate"|"high">,
    "direction": <"positive"|"negative"|"neutral"|"mixed">
  }},
  "geographic_mentions": [
    {{
      "region": <string, standardized region name like "US_Southeast", "Inland_Empire", "Dallas_Fort_Worth", "Indianapolis", "Midwest">,
      "confidence": <float 0.0-1.0>,
      "context": <string, brief note on what was said about this location>
    }}
  ],
  "signals": {{
    "capex_expansion": <bool, is capital expenditure for warehouse/DC expansion mentioned?>,
    "demand_strength": <"increasing"|"stable"|"decreasing">,
    "vacancy_mention": <bool, is warehouse vacancy discussed?>,
    "rent_pressure": <"upward"|"neutral"|"downward">,
    "construction_pipeline": <"active"|"moderate"|"none">,
    "automation_investment": <bool, warehouse automation investment mentioned?>,
    "network_redesign": <bool, supply chain or distribution network restructuring discussed?>,
    "build_to_suit": <bool, build-to-suit warehouse projects mentioned?>,
    "last_mile_expansion": <bool, last-mile or regional fulfillment expansion discussed?>
  }},
  "evidence_quote": <string, the single most important sentence or phrase from the text supporting your scores. Copy it verbatim.>,
  "reasoning": <string, 1-2 sentences explaining your warehouse_relevance and expansion_score ratings>
}}

Scoring guidance:
- warehouse_relevance: 0.0 for pure financial discussion with no logistics mention. 0.3-0.5 for passing references to supply chain. 0.6-0.8 for substantive discussion of warehouse/DC topics. 0.9-1.0 for detailed plans with square footage, capex, or specific facility commitments.
- expansion_score: Weight forward-looking statements higher than historical. Specific commitments (dollar amounts, square footage, groundbreaking) score higher than vague intentions. Consolidation should still score moderate expansion_score if net square footage increases.
- geographic_mentions: Only include regions mentioned in the context of warehouse/logistics activity. Standardize to metro areas or US regions (US_Southeast, US_Midwest, etc.). Do NOT include regions mentioned only in a sales/revenue context."""


def format_system_prompt(
    ticker: str, company_name: str, year: int, quarter: int, section_type: str
) -> str:
    return SYSTEM_PROMPT.format(
        ticker=ticker,
        company_name=company_name,
        year=year,
        quarter=quarter,
        section_type=section_type,
    )


def format_extraction_prompt(chunk_text: str) -> str:
    return EXTRACTION_PROMPT.format(chunk_text=chunk_text)

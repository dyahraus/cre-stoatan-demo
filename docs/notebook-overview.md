# Pipeline Walkthrough Notebook — Section-by-Section Overview

Reference: `warehouse-signal/notebooks/pipeline-walkthrough.ipynb`

This document maps each notebook section to the backend modules it exercises, the data it produces, and how it fits into the end-to-end pipeline.

---

## 1. Setup & Configuration

**Cells:** 2–3
**Backend modules:** `warehouse_signal.config.Config`, `warehouse_signal.storage.sqlite.Storage`

### What it does

- **Cell 2** — Prints `sys.executable` and `sys.prefix` to verify the notebook is running inside the `warehouse-signal` virtualenv (`.venv/bin/python`). This is the first sanity check — if these paths point elsewhere, imports like `sqlite_utils` will fail with `ModuleNotFoundError`.

- **Cell 3** — Instantiates `Storage()` which:
  1. Reads `DATABASE_PATH` from `Config` (defaults to `data/warehouse_signal.db`)
  2. Creates the parent directory if needed
  3. Opens a SQLite connection via `sqlite_utils.Database`
  4. Calls `_ensure_tables()` to create all 5 tables if they don't exist: `companies`, `transcripts`, `chunks`, `signal_extractions`, `company_scores`
  5. Calls `get_stats()` which returns row counts for each table

### Backend mapping

| Call | Source file | Method |
|------|------------|--------|
| `Storage()` | `storage/sqlite.py:31-37` | `__init__` — connects to SQLite, runs `_ensure_tables()` |
| `storage.get_stats()` | `storage/sqlite.py:414-424` | Queries `COUNT(*)` on each table |

### Expected output

A dictionary showing 0 counts across all tables (fresh database), or existing counts if the DB was previously populated.

---

## 2. Universe — What Companies We Track

**Cell:** 5
**Backend modules:** `warehouse_signal.universe.sp500`

### What it does

Calls `get_universe()` which delegates to `fetch_sp500_tickers()`. The resolution order is:

1. **Cached file** — checks `data/sp500_companies.json`. If it exists, deserializes and returns immediately.
2. **FMP API** — if `FMP_API_KEY` is set, fetches from `https://financialmodelingprep.com/api/v3/sp500_constituent`, maps GICS sub-industries to our `Sector` enum via `_infer_sector()`, and caches the result.
3. **Hardcoded watchlist** — falls back to `_get_core_watchlist()`, a curated 30-ticker list of warehouse-heavy companies (industrial REITs, 3PLs, e-commerce, retail, food distribution, automotive, manufacturing).

After fetching, the cell prints sector distribution using `Counter` and a sample of the first 10 companies.

### Backend mapping

| Call | Source file | Method |
|------|------------|--------|
| `get_universe()` | `universe/sp500.py:158-160` | Async wrapper around `fetch_sp500_tickers()` |
| `fetch_sp500_tickers()` | `universe/sp500.py:56-102` | Cache → FMP API → hardcoded fallback |
| `_infer_sector()` | `universe/sp500.py:47-53` | Keyword matching against `_SECTOR_KEYWORDS` dict |
| `_get_core_watchlist()` | `universe/sp500.py:105-155` | Returns 30 hardcoded `Company` objects |

### Data model

Each company is a `Company` pydantic model (`models/schemas.py:47-57`) with fields: `ticker`, `name`, `sector` (enum), `cik`, `sp500`, `geo_exposure`, `active`.

---

## 3. Transcript Providers — Mock vs FMP

**Cells:** 7–9
**Backend modules:** `warehouse_signal.providers.mock.MockProvider`, `warehouse_signal.providers.fmp.FMPProvider`, `warehouse_signal.providers.base.TranscriptProvider`

### What it does

Demonstrates both transcript sources side-by-side.

**Cell 7 — MockProvider:**
- Calls `MockProvider.get_transcript("PLD", 2024, 3)`
- Looks up the ticker in `_TICKER_SIGNAL_MAP` — PLD maps to `"high"`, selecting the `_HIGH_SIGNAL` template (a synthetic ~1,424 char transcript with dense warehouse keywords: distribution centers, capex, build-to-suit, last-mile, square footage)
- Returns a `Transcript` with one pre-labeled `prepared_remarks` section
- Prints metadata, section count, content length, and the full transcript text

**Cell 8 — FMPProvider:**
- Instantiates `FMPProvider()` which reads `FMP_API_KEY` from `Config` and creates an `httpx.AsyncClient`
- Calls `fmp_provider.get_transcript("PLD", 2024, 3)` which hits `GET /stable/earning-call-transcript?symbol=PLD&quarter=3&year=2024&apikey=...`
- Parses the response: extracts `content` as `raw_text`, parses `date` field into `call_date`
- Returns a `Transcript` with one `full` (unsegmented) section — the entire ~50K char earnings call
- Prints metadata, content length, and the first 500 characters

**Cell 9 — Available transcripts:**
- Calls `fmp_provider.list_available_transcripts("PLD", start_year=2023, end_year=2024)`
- This probes each quarter individually (8 API calls: 4 quarters x 2 years) since the FMP stable API requires both `year` and `quarter` params
- Returns a list of `TranscriptMetadata` objects for each quarter that has data

### Backend mapping

| Call | Source file | Method |
|------|------------|--------|
| `MockProvider.get_transcript()` | `providers/mock.py:117-143` | Template lookup by ticker → signal level |
| `FMPProvider.get_transcript()` | `providers/fmp.py:72-114` | HTTP GET to FMP stable API |
| `FMPProvider.list_available_transcripts()` | `providers/fmp.py:116-154` | Probes each quarter via GET |
| `FMPProvider._get()` | `providers/fmp.py:52-66` | Retry-wrapped HTTP client with 3 attempts |

### Provider interface

Both implement `TranscriptProvider` (`providers/base.py:19-79`), which defines:
- `get_transcript(ticker, year, quarter) -> Transcript | None`
- `list_available_transcripts(ticker) -> list[TranscriptMetadata]`
- `get_earnings_calendar(from_date, to_date) -> list[EarningsEvent]`
- `close()` — cleanup for HTTP clients

---

## 4. Parsing — Section Detection

**Cell:** 11
**Backend module:** `warehouse_signal.ingestion.parser.parse_sections`

### What it does

Runs `parse_sections(real_transcript)` on the FMP transcript. This function:

1. Checks if the transcript already has non-`FULL` sections (e.g., if the provider pre-segmented it). If so, returns immediately — this is a no-op for MockProvider transcripts which arrive pre-labeled.
2. For unsegmented transcripts (FMP), searches the raw text for Q&A boundary patterns using 6 compiled regexes (`_QA_BOUNDARY_PATTERNS` at `parser.py:27-34`). These match phrases like:
   - "operator, open the line for questions"
   - "let's open it up for questions"
   - "question-and-answer session"
   - "we will now take your questions"
3. If a match is found at position > 200 chars (sanity check), splits into two `TranscriptSection` objects: `PREPARED_REMARKS` (before the match) and `QA` (from the match onward).
4. If no match is found, keeps the entire text as a single `FULL` section.

The cell prints how many sections were found, whether structured sections exist, and a preview of each section's type and length.

### Backend mapping

| Call | Source file | Function |
|------|------------|----------|
| `parse_sections()` | `ingestion/parser.py:43-89` | Regex-based Q&A boundary detection |
| `_QA_BOUNDARY_PATTERNS` | `ingestion/parser.py:27-34` | 6 compiled regexes for transition phrases |

### Known issue

The PLD Q3 2024 transcript from FMP did not match any of the 6 Q&A boundary patterns — it came through as a single `full` section (1 section, 50,281 chars). The actual FMP transcript uses `[Operator Instructions]` style formatting for the Q&A transition, which none of the current regexes capture.

---

## 5. Chunking — Breaking Text Into Analysis Units

**Cell:** 13
**Backend module:** `warehouse_signal.ingestion.parser.chunk_transcript`

### What it does

Calls `chunk_transcript(real_transcript)` which splits each section into LLM-sized chunks:

1. Reads target and max token settings from `Config` (defaults: `CHUNK_TARGET_TOKENS=800`, `CHUNK_MAX_TOKENS=1200`)
2. For each section, splits text into paragraphs via `_split_paragraphs()` (splits on double newlines)
3. Accumulates paragraphs into a buffer until adding the next paragraph would exceed the target token count
4. When the target is exceeded, flushes the buffer as a `TranscriptChunk` and starts a new one
5. If a single paragraph exceeds `max_tokens`, falls back to `_split_by_sentences()` which groups sentences to stay near the target
6. Each chunk gets a deterministic ID via `SHA256(transcript_key::chunk_index)[:16]`
7. Token estimation uses the heuristic `len(text.split()) * 1.33` (~0.75 tokens per word)

The cell prints total chunk count, token distribution (min/max/avg), config targets, and previews of the first 3 chunks.

### Backend mapping

| Call | Source file | Function |
|------|------------|----------|
| `chunk_transcript()` | `ingestion/parser.py:107-177` | Main chunking loop |
| `_split_paragraphs()` | `ingestion/parser.py:200-203` | Splits on `\n\s*\n` |
| `_split_by_sentences()` | `ingestion/parser.py:206-226` | Splits on `(?<=[.!?])\s+` |
| `_build_chunk()` | `ingestion/parser.py:180-197` | Constructs `TranscriptChunk` with deterministic ID |
| `_estimate_tokens()` | `ingestion/parser.py:96-98` | Word count * 1.33 |
| `_make_chunk_id()` | `ingestion/parser.py:101-104` | SHA256 hash truncated to 16 hex chars |

### PLD Q3 2024 results

- 15 chunks produced from the 50,281-char transcript
- Token range: 113–829 (avg 762), well within the 800 target / 1200 max
- All chunks labeled `full` section type (since parsing didn't detect a Q&A boundary)

---

## 6. Signal Extraction — Mock vs Claude

**Cells:** 15–19
**Backend modules:** `warehouse_signal.analysis.mock.MockAnalyzer`, `warehouse_signal.analysis.extractor.ClaudeAnalyzer`, `warehouse_signal.analysis.prompt`

### What it does

Analyzes a single chunk through both extraction backends and compares results.

**Cell 15** — Selects `chunks[0]` as the test chunk and prints a preview.

**Cell 16 — MockAnalyzer:**
- Counts keyword hits from `_WAREHOUSE_KEYWORDS` (14 terms: warehouse, distribution center, logistics, fulfillment, sq ft, capex, etc.)
- Computes `warehouse_relevance = min(hits / 5, 1.0)` and `expansion_score = min(hits / 7, 1.0)`
- Sets `move_type` based on hit count (>=3 → expansion, >=1 → optimization)
- Detects geographies via 5 hardcoded regexes (`_GEO_PATTERNS`: Inland Empire, Indianapolis, DFW, Southeast, Midwest)
- Sets signal flags by checking for specific keywords (capex, build-to-suit, last-mile, automation, etc.)
- Returns a fully deterministic `ChunkExtraction`

**Cell 17 — ClaudeAnalyzer:**
- Constructs a system prompt via `format_system_prompt()` identifying the company, quarter, and section type
- Constructs a user prompt via `format_extraction_prompt()` wrapping the chunk text in `<transcript_chunk>` tags and providing the full JSON schema with scoring guidance
- Calls the Anthropic API (`messages.create()`) with `model=claude-haiku-4-5-20251001` and `max_tokens=1024`
- Has retry logic via `tenacity`: 3 attempts with exponential backoff (2-30s) for rate limits and server errors
- Parses the JSON response (stripping markdown fences if present) into a `ChunkExtraction`
- On failure, returns a zeroed-out extraction with the error message in `reasoning`

**Cell 18** — Side-by-side comparison table of mock vs Claude results for the same chunk.

**Cell 19** — Prints the actual system and user prompts sent to Claude, useful for prompt engineering iteration.

### Backend mapping

| Call | Source file | Method/Function |
|------|------------|----------------|
| `MockAnalyzer.extract_signals()` | `analysis/mock.py:44-110` | Keyword counting + regex geo detection |
| `ClaudeAnalyzer.extract_signals()` | `analysis/extractor.py:50-76` | Builds prompts → API call → parse JSON |
| `ClaudeAnalyzer._call_api()` | `analysis/extractor.py:41-48` | Retry-wrapped `messages.create()` |
| `_parse_json()` | `analysis/extractor.py:82-88` | Strips markdown fences, `json.loads()` |
| `format_system_prompt()` | `analysis/prompt.py:55-64` | Template with company/quarter context |
| `format_extraction_prompt()` | `analysis/prompt.py:67-68` | Template with chunk text + JSON schema + scoring guidance |

### Analyzer interface

Both implement `SignalAnalyzer` (`analysis/base.py:10-39`), which defines:
- `name` property — identifier string (`"mock"` or `"claude"`)
- `extract_signals(chunk, ticker, company_name, year, quarter) -> ChunkExtraction`
- `close()` — cleanup (ClaudeAnalyzer closes the httpx client)
- Supports async context manager (`async with`)

### Data model — ChunkExtraction

Defined at `models/schemas.py:189-199`:

| Field | Type | Description |
|-------|------|-------------|
| `warehouse_relevance` | float 0-1 | How relevant the chunk is to warehouse/logistics RE |
| `expansion_score` | float 0-1 | Strength of expansion signal |
| `move_type` | MoveType enum | expansion / consolidation / relocation / optimization / no_change / unknown |
| `time_horizon` | TimeHorizon enum | immediate / near_term / medium_term / long_term / historical / unspecified |
| `sentiment` | Sentiment | polarity (-1 to 1), intensity, direction |
| `geographic_mentions` | list[GeographicMention] | region name, confidence, context string |
| `signals` | SignalFlags | 9 boolean/categorical flags (capex, BTS, last-mile, automation, etc.) |
| `evidence_quote` | str | Verbatim key sentence from the text |
| `reasoning` | str | 1-2 sentence explanation of the scores |

---

## 7. Full Ingestion + Analysis Pipeline

**Cells:** 21–24
**Backend modules:** `warehouse_signal.ingestion.pipeline`, `warehouse_signal.analysis.pipeline`

### What it does

Runs the complete two-stage pipeline against a fresh demo database (`data/notebook_demo.db`).

**Cell 21 — Stage 1: Ingestion** via `ingest_transcript()`:
1. Checks `storage.has_transcript()` — skips if already stored (bypassed here with `force=True`)
2. Calls `provider.get_transcript()` to fetch from FMP
3. Calls `parse_sections()` to detect prepared remarks vs Q&A boundary
4. Calls `chunk_transcript()` to split into LLM-sized chunks
5. Calls `storage.save_transcript()` — upserts into `transcripts` table with `processed=0`
6. Calls `storage.save_chunks()` — upserts each chunk into `chunks` table
7. Returns the `Transcript` object

**Cell 22** — Queries `demo_storage.get_chunks_for_transcript("PLD_2024Q3")` to verify chunks were persisted to SQLite, ordered by `chunk_index`.

**Cell 23 — Stage 2: Analysis** via `analyze_transcript()`:
1. Fetches all chunk rows from DB for the transcript
2. Looks up company name via `storage.get_company_name()`
3. Iterates through each chunk row, reconstructing a `TranscriptChunk` pydantic model
4. Calls `analyzer.extract_signals()` on each chunk (15 sequential API calls to Claude)
5. Calls `storage.save_extraction()` for each result — stores scores, signals JSON, geographic mentions JSON, and the full `raw_llm_output` (the complete `ChunkExtraction` serialized as JSON)
6. Calls `storage.mark_processed(quarter_key)` — sets `processed=1` in the `transcripts` table

**Cell 24** — Queries `demo_storage.get_extractions_for_transcript("PLD_2024Q3")`, sorts by `expansion_score` descending, and prints the top 5 with evidence quotes parsed from `raw_llm_output`.

### Backend mapping

| Call | Source file | Method |
|------|------------|--------|
| `ingest_transcript()` | `ingestion/pipeline.py:24-55` | Fetch → parse → chunk → store |
| `analyze_transcript()` | `analysis/pipeline.py:22-67` | Load chunks → extract signals → save → mark processed |
| `storage.save_transcript()` | `storage/sqlite.py:199-226` | Upserts transcript row with sections as JSON |
| `storage.save_chunks()` | `storage/sqlite.py:228-242` | Upserts each chunk row |
| `storage.save_extraction()` | `storage/sqlite.py:280-312` | Upserts extraction with scores + full JSON |
| `storage.mark_processed()` | `storage/sqlite.py:253-254` | Sets `processed=1` flag |
| `storage.get_extractions_for_transcript()` | `storage/sqlite.py:314-320` | WHERE `transcript_key = ?` |

### Database state after both stages

| Table | Rows | Notes |
|-------|------|-------|
| `companies` | 1 | PLD (auto-inserted or from prior run) |
| `transcripts` | 1 | PLD_2024Q3, `processed=0→1` |
| `chunks` | 15 | All `full` section type |
| `signal_extractions` | 15 | One per chunk, keyed by `chunk_id` |
| `company_scores` | 1 | From prior run (overwritten in Section 8) |

---

## 8. Scoring — From Chunks to Company Score

**Cells:** 26–27
**Backend module:** `warehouse_signal.scoring.aggregator`

### What it does

**Cell 26** — Calls `score_company(demo_storage, "PLD")` which aggregates all chunk-level extractions into a single `CompanyScore`:

1. Fetches all extractions for the ticker via `storage.get_extractions_for_ticker()` (joins `signal_extractions` with `transcripts` on `quarter_key` to filter by ticker)
2. Filters to "relevant" chunks: `warehouse_relevance >= RELEVANCE_THRESHOLD` (0.3)
3. Computes the composite score via `compute_composite_score()`:
   - **40% — Peak signal:** `max(expansion_score)` across relevant chunks
   - **30% — Breadth:** weighted average of `expansion_score`, weighted by `warehouse_relevance`
   - **15% — Signal flags:** 0.05 bonus each for `capex_expansion`, `build_to_suit`, `last_mile_expansion` (parsed from `signals_json`)
   - **15% — Time horizon:** average of per-chunk time weights (immediate=1.0, near_term=0.8, medium_term=0.5, long_term=0.3, historical=0.1, unspecified=0.2)
4. Aggregates geographic mentions across all relevant chunks using `Counter`, takes top 5
5. Determines dominant `move_type` and `time_horizon` via mode (most common value)
6. Extracts top 3 evidence quotes from the highest-scoring chunks (parsed from `raw_llm_output`)

**Cell 27** — Manually recomputes each formula component with actual numbers to show the math:
- Lists relevant chunk count vs total
- Shows each component's raw value and weighted contribution
- Sums to the final composite score

### Backend mapping

| Call | Source file | Function |
|------|------------|----------|
| `score_company()` | `scoring/aggregator.py:76-165` | Full aggregation: filter → composite → geo → evidence |
| `compute_composite_score()` | `scoring/aggregator.py:30-73` | The 4-component formula |
| `RELEVANCE_THRESHOLD` | `scoring/aggregator.py:17` | 0.3 |
| `TIME_WEIGHTS` | `scoring/aggregator.py:20-27` | Dict mapping time horizon strings to floats |

### PLD Q3 2024 score

| Component | Weight | Value | Contribution |
|-----------|--------|-------|-------------|
| Max expansion | 40% | 0.720 | 0.288 |
| Weighted avg expansion | 30% | 0.537 | 0.161 |
| Signal flag bonus | 15% | 0.150 (3/3 flags) | 0.023 |
| Time horizon bonus | 15% | 0.564 | 0.085 |
| **Composite** | | | **0.556** |

14 of 15 chunks were relevant. Dominant move type: expansion. Dominant time horizon: medium_term. All three signal flags triggered (capex, BTS, last-mile). Top geographies: Southern California, Mexico, Inland Empire.

---

## 9. API Layer — What the Frontend Sees

**Cells:** 29–32
**Backend modules:** `warehouse_signal.api.routes`, `warehouse_signal.scoring.aggregator`, `warehouse_signal.storage.sqlite`

### What it does

Calls the same underlying functions that the FastAPI routes use, showing exactly what the frontend receives.

**Cell 29 — `GET /api/stats`:**
- Calls `demo_storage.get_stats()` → returns row counts for all 5 tables
- Route handler: `api_stats()` at `api/routes.py:22-25`

**Cell 30 — `GET /api/scores/PLD`:**
- Calls `score_company(demo_storage, "PLD")` → returns a fresh `CompanyScore` computed from current extractions
- Serializes via `pld_score.model_dump(mode='json')` — this is the exact JSON the frontend receives
- Route handler: `api_score_detail(ticker)` at `api/routes.py:69-76`

**Cell 31 — `GET /api/scores/PLD/extractions`:**
- Calls `demo_storage.get_extractions_for_ticker("PLD")` → returns raw DB rows with JSON string fields
- In the actual API route (`api/routes.py:79-99`), these JSON strings are parsed into objects for the frontend: `geographic_mentions`, `signals_json`, `evidence_quote`, `reasoning`
- Shows the top 3 chunks sorted by `expansion_score`

**Cell 32 — `GET /api/geographies`:**
- Saves the PLD score to the `company_scores` table via `demo_storage.save_company_score()`
- Fetches all scores, converts to `CompanyScore` models via `row_to_company_score()`
- Aggregates geographies across all scored companies: for each region, computes average score and company count
- Route handler: `api_geographies()` at `api/routes.py:102-135`
- With only PLD in the DB, all 5 geographies show avg=0.556

### Backend mapping — API routes

| Endpoint | Route handler | Source |
|----------|--------------|--------|
| `GET /api/stats` | `api_stats()` | `api/routes.py:22-25` |
| `GET /api/scores` | `api_scores()` | `api/routes.py:28-66` — supports filtering by min_score, sector, geography, move_type, time_horizon |
| `GET /api/scores/{ticker}` | `api_score_detail()` | `api/routes.py:69-76` |
| `GET /api/scores/{ticker}/extractions` | `api_extractions()` | `api/routes.py:79-99` |
| `GET /api/geographies` | `api_geographies()` | `api/routes.py:102-135` |
| `GET /api/enums` | `api_enums()` | `api/routes.py:138-145` — returns valid values for filter dropdowns |

### Server setup

- FastAPI app defined in `api/server.py:19-33`
- CORS configured for `http://localhost:3000` (the Next.js frontend)
- All routes prefixed with `/api`
- Storage initialized via lifespan handler (`api/deps.py`) — singleton pattern

---

## 10. Summary & Cleanup

**Cells:** 33–34

**Cell 33** — Markdown comparison table: mock mode vs real mode across 7 dimensions (transcript source, section parsing, chunking, signal extraction, geographic detection, scoring formula, API cost).

**Cell 34** — Calls `await fmp_provider.close()` and `await claude_analyzer.close()` to clean up HTTP clients. `FMPProvider.close()` calls `self._client.aclose()` on the httpx client. `ClaudeAnalyzer.close()` calls `self._client.close()` on the Anthropic async client.

---

## End-to-End Data Flow

```
                    Cell 8                     Cell 11                    Cell 13
FMP API ──────► get_transcript() ──────► parse_sections() ──────► chunk_transcript()
                     │                         │                         │
                     ▼                         ▼                         ▼
               Transcript              TranscriptSection(s)      TranscriptChunk(s)
               (raw_text,              (PREPARED_REMARKS          (chunk_id, text,
                metadata)               or QA or FULL)             ~800 tokens each)
                     │                                                   │
                     │              Cell 21                               │
                     └────────► save_transcript() ◄──────────────────────┘
                                save_chunks()         Cell 17 / Cell 23
                                     │            ┌──► extract_signals()
                                     ▼            │         │
                                  SQLite DB       │         ▼
                                     │            │   ChunkExtraction
                                     │            │   (relevance, expansion,
                                     │            │    move_type, signals,
                                     │            │    geography, evidence)
                                     │            │         │
                                     ▼            │         ▼
                              get_chunks() ───────┘   save_extraction()
                                                           │
                                                           ▼
                              Cell 26                   SQLite DB
                         score_company() ◄─── get_extractions_for_ticker()
                              │
                              ▼
                        CompanyScore
                        (composite 0-1,
                         top geographies,
                         signal flags,
                         evidence snippets)
                              │
                              ▼
                     Cell 30–32: API JSON
                     (what the frontend fetches)
```

---

## File Reference

| Notebook section | Primary source files |
|-----------------|---------------------|
| 1. Setup | `config.py`, `storage/sqlite.py` |
| 2. Universe | `universe/sp500.py` |
| 3. Providers | `providers/mock.py`, `providers/fmp.py`, `providers/base.py` |
| 4. Parsing | `ingestion/parser.py` (lines 27-89) |
| 5. Chunking | `ingestion/parser.py` (lines 96-226) |
| 6. Extraction | `analysis/mock.py`, `analysis/extractor.py`, `analysis/prompt.py`, `analysis/base.py` |
| 7. Pipeline | `ingestion/pipeline.py`, `analysis/pipeline.py` |
| 8. Scoring | `scoring/aggregator.py` |
| 9. API | `api/routes.py`, `api/server.py`, `api/deps.py` |

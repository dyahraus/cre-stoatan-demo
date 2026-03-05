# Pipeline Demo Page

Interactive walkthrough of the Warehouse Signal extraction pipeline. Accessible at `/demo` in the frontend sidebar. Users select a real earnings call transcript, then step through each stage of the pipeline with manual button clicks, watching the LLM stream its analysis in real time.

---

## Overview

The demo page presents 5 sequential steps as collapsible cards:

1. **Select Transcript** — pick one of 3 cached earnings transcripts
2. **Parse Sections** — detect prepared remarks vs Q&A boundaries
3. **Chunk Transcript** — split into ~800-token chunks
4. **Extract Signals** — stream LLM analysis (supports multi-chunk)
5. **Composite Score** — see the scoring formula breakdown

Each step has three visual states: **locked** (dimmed, not interactive), **active** (blue border, expanded), and **completed** (green check, collapsed with summary). Selecting a new transcript resets all downstream steps.

---

## Demo Transcripts

Three hardcoded earnings call transcripts, fetched from FMP on first load and cached in the SQLite database:

| Ticker | Company | Quarter | Sector | Why Included |
|--------|---------|---------|--------|--------------|
| PLD | Prologis Inc | 2024 Q3 | REIT Industrial | Industrial REIT, strong warehouse signals |
| WMT | Walmart Inc | 2024 Q3 | Retail | Massive DC operations, supply chain focus |
| HD | The Home Depot | 2024 Q3 | Retail | Home improvement, distribution network |

After the initial FMP fetch (~5s), transcripts load instantly from the database on subsequent visits. The backend validates cached transcripts are real FMP data (provider == "fmp" and length > 5000 chars) before serving them.

---

## Step-by-Step Functionality

### Step 1: Select Transcript

**UI:** 3-card grid showing ticker, company name, quarter, call date, and character count. Selected card gets a blue border highlight.

**Action:** Click a transcript card, then click "Parse Sections" to proceed.

**API:** `GET /api/demo/transcripts` returns the 3 demo transcripts. On first call, fetches from FMP and caches. Returns `ticker`, `company_name`, `year`, `quarter`, `quarter_key`, `raw_text_length`, `call_date`.

### Step 2: Parse Sections

**UI:** Shows how many sections were detected, whether a Q&A boundary was found (badge), and the full text of each section in a scrollable container (max-height 200px, overflow scroll). Each section shows its type badge and character count.

**Action:** Review the parsed sections, then click "Chunk Transcript" to proceed.

**API:** `GET /api/demo/parse?quarter_key=PLD_2024Q3` — Reconstructs a `Transcript` pydantic model from the DB row, runs `parse_sections()` from `ingestion/parser.py`. Returns the full section text (no truncation), section type, and text length for each detected section, plus a `boundary_found` boolean.

**Backend detail:** The parser uses 6 regex patterns to detect Q&A transition boundaries. Some transcripts (e.g., PLD Q3 2024) may not match any pattern, in which case the entire text is treated as a single "full" section.

### Step 3: Chunk Transcript

**UI:** Summary stats (total chunks, average tokens), then a scrollable table with columns: chunk index, section type badge, token count, and text preview. Rows are clickable to toggle selection (multi-select). A "Select All / Deselect All" link toggles all chunks. A blue counter shows how many chunks are currently selected.

**Actions:**
- Click individual rows to toggle selection (multi-select, sorted by index)
- "Run Extraction (N chunks)" — extract only selected chunks
- "Run All Chunks" — selects all chunks and starts extraction on every one

**API:** `GET /api/demo/chunks?quarter_key=PLD_2024Q3` — Loads chunks from `storage.get_chunks_for_transcript()`. Returns each chunk's `chunk_index`, `chunk_id`, `section_type`, `token_estimate`, `text_preview` (first 200 chars), and full `text`. Also returns `total_chunks` and `avg_tokens`.

### Step 4: Extract Signals

**UI:** Three sections:

1. **Prompt Preview** — shows a truncated version of the user prompt sent to the LLM (first 300 chars)
2. **Streaming Terminal** — dark background, green monospace text that streams in token-by-token with a blinking cursor. Terminal header shows macOS-style traffic light dots, "LLM Response" label, and current chunk label when running multi-chunk. When processing multiple chunks, separator lines (`--- Chunk N (M/total) ---`) appear between each chunk's output.
3. **Parsed Extraction Cards** — one card per completed extraction, each showing:
   - Warehouse relevance and expansion score (progress bars)
   - Move type and time horizon (outline badges)
   - Signal flags: CAPEX, BTS, Last-Mile (colored badges, shown when true)
   - Geographic mentions (secondary badges)
   - Evidence quote (italic, left-bordered)
   - Reasoning text

**Multi-chunk behavior:** Chunks are extracted sequentially. The `runNext()` function chains each stream's `onDone` callback to start the next chunk. Stream text accumulates with separators. Each extraction result is appended to an array and rendered as a separate card. The streaming terminal auto-scrolls to the bottom as new tokens arrive.

**Action:** After all extractions complete, click "Compute Score" to proceed.

**API:** `GET /api/demo/extract/stream?quarter_key=PLD_2024Q3&chunk_index=0` — Server-Sent Events endpoint. Sends the following SSE event types in order:

| Event Type | Payload | Description |
|------------|---------|-------------|
| `chunk_info` | `{chunk_index, section_type, token_estimate}` | Metadata about the chunk being processed |
| `prompt` | `{system, user_preview}` | Full system prompt and truncated user prompt |
| `token` | `{text}` | Individual token from LLM stream (many events) |
| `extraction` | `{data: <ChunkExtraction>}` | Parsed structured extraction after stream completes |
| `done` | `{}` | Stream finished successfully |
| `error` | `{message}` | Error occurred (API key missing, parse failure, etc.) |

**Backend detail:** Creates an `AsyncAnthropic` client, calls `messages.stream()` with the configured model and max tokens. Accumulates the full response text, then parses it with `_parse_json()` (strips markdown fences) and validates through the `ChunkExtraction` pydantic model. Response headers include `Cache-Control: no-cache` and `X-Accel-Buffering: no` to prevent proxy buffering.

### Step 5: Composite Score

**UI:** Four sections:

1. **Composite Score** — large percentage display with progress bar. Shows a note if below relevance threshold.
2. **Formula Breakdown** — 4 component cards, each showing:
   - Component name and weight (Max Expansion 40%, Weighted Avg 30%, Flag Bonus 15%, Time Bonus 15%)
   - Raw value progress bar
   - Calculation: `raw value x weight = contribution`
   - Flag details (for flag bonus) or time horizon (for time bonus)
3. **Extraction Input** — grid showing the first extraction's relevance, expansion, move type, time horizon, and evidence quote
4. **Note** — contextual message about single vs multi-chunk scoring

**API:** `POST /api/demo/score` with body `{quarter_key, extractions: [...]}` — accepts an array of extraction dicts. When multiple extractions are provided:
- `max_expansion`: highest expansion score across all extractions
- `weighted_avg`: relevance-weighted average of expansion scores (only relevant chunks)
- `flag_bonus`: union of all signal flags across extractions (0.05 per flag)
- `time_bonus`: best time horizon weight across all extractions
- Composite score is computed by `compute_composite_score()` from `scoring/aggregator.py`

---

## Architecture

### Data Flow

```
Frontend (Next.js)                    Backend (FastAPI)                   External
     |                                      |                               |
     |--GET /api/demo/transcripts---------->|                               |
     |                                      |--FMP API (first load only)--->|
     |                                      |<--transcript JSON-------------|
     |                                      |--SQLite cache (subsequent)--->|
     |<--[{ticker, company, ...}]-----------|                               |
     |                                      |                               |
     |--GET /api/demo/parse?quarter_key=--->|                               |
     |                                      |--parse_sections()             |
     |<--{sections, boundary_found}---------|                               |
     |                                      |                               |
     |--GET /api/demo/chunks?quarter_key=-->|                               |
     |                                      |--SQLite: get_chunks_for_*     |
     |<--{chunks, total_chunks, avg_tokens}-|                               |
     |                                      |                               |
     |--GET /api/demo/extract/stream------->|                               |
     |                                      |--messages.stream()----------->|
     |<--SSE: token, token, token, ...------|<--token stream----------------|
     |<--SSE: extraction--------------------|                               |
     |<--SSE: done--------------------------|                               |
     |                                      |                               |
     |--POST /api/demo/score--------------->|                               |
     |                                      |--compute_composite_score()    |
     |<--{composite_score, components, ...}-|                               |
```

### SSE Streaming Path

```
Anthropic API  -->  FastAPI StreamingResponse  -->  Next.js rewrite proxy  -->  Browser fetch() ReadableStream
```

The Next.js `next.config.ts` rewrites `/api/*` to `localhost:8000`, proxying SSE transparently without buffering. The frontend uses `fetch()` with a `ReadableStream` reader, splits on `\n\n` to parse SSE frames, and dispatches each `data:` payload to typed callbacks.

For multi-chunk extraction, the frontend chains streams sequentially: each chunk's `onDone` callback increments a counter and calls `runNext()`. An `AbortController` ref allows cancellation on unmount.

---

## File Reference

### Backend

| File | Description |
|------|-------------|
| `warehouse-signal/src/warehouse_signal/api/demo_routes.py` | All 5 demo endpoints (APIRouter with `/demo` prefix) |
| `warehouse-signal/src/warehouse_signal/api/server.py` | Includes the demo router (`app.include_router(demo_router, prefix="/api")`) |
| `warehouse-signal/src/warehouse_signal/ingestion/parser.py` | `parse_sections()` — section boundary detection with regex patterns |
| `warehouse-signal/src/warehouse_signal/ingestion/pipeline.py` | `ingest_transcript()` — fetches from FMP, stores in DB, chunks automatically |
| `warehouse-signal/src/warehouse_signal/analysis/prompt.py` | `format_system_prompt()`, `format_extraction_prompt()` — prompt construction |
| `warehouse-signal/src/warehouse_signal/analysis/extractor.py` | `_parse_json()` — strips markdown fences from LLM output |
| `warehouse-signal/src/warehouse_signal/scoring/aggregator.py` | `compute_composite_score()`, `RELEVANCE_THRESHOLD`, `TIME_WEIGHTS` |
| `warehouse-signal/src/warehouse_signal/models/schemas.py` | `ChunkExtraction` pydantic model (validates parsed LLM output) |

### Frontend

| File | Description |
|------|-------------|
| `frontend/src/app/demo/page.tsx` | Main page — state machine, step progression, multi-chunk orchestration |
| `frontend/src/components/demo/step-card.tsx` | Reusable step wrapper (locked/active/completed states) |
| `frontend/src/components/demo/transcript-selector.tsx` | 3-card transcript picker grid |
| `frontend/src/components/demo/parse-display.tsx` | Section detection results with scrollable full-text preview |
| `frontend/src/components/demo/chunk-display.tsx` | Multi-select chunk table with Select All/Deselect All |
| `frontend/src/components/demo/extraction-stream.tsx` | Streaming terminal + parsed extraction result cards |
| `frontend/src/components/demo/score-display.tsx` | Composite score with formula breakdown bars |
| `frontend/src/lib/api.ts` | Demo API functions: `fetchDemoTranscripts`, `fetchDemoParse`, `fetchDemoChunks`, `fetchDemoScore`, `streamDemoExtraction` |
| `frontend/src/lib/types.ts` | TypeScript interfaces: `DemoTranscript`, `DemoParseResult`, `DemoChunkResult`, `DemoScoreResult`, etc. |
| `frontend/src/components/layout/sidebar.tsx` | Nav item entry for `/demo` with beaker icon |

---

## State Management

The demo page uses a linear state machine with 5 steps. All state lives in the page component via `useState` hooks:

```
step: DemoStep          — current active step ("select" | "parse" | "chunk" | "extract" | "score")
transcripts             — 3 demo transcripts (loaded on mount)
selected                — currently selected transcript
parseResult             — section detection output
chunkResult             — chunk breakdown output
selectedChunkIndices    — array of selected chunk indices (multi-select)
streamText              — accumulated raw LLM token text
isStreaming             — whether an SSE stream is active
extractions             — array of parsed ChunkExtraction objects
promptPreview           — truncated prompt shown above the terminal
currentChunkLabel       — "Chunk N (M/total)" shown in terminal header
scoreResult             — composite score and formula breakdown
loading                 — general loading flag for non-streaming requests
error                   — dismissible error message
abortRef                — AbortController ref for cancelling active streams
```

The `resetFrom(step)` function clears all state from a given step onward, ensuring downstream results are invalidated when upstream inputs change.

---

## Scoring Formula

The composite score aggregates extraction results using 4 weighted components:

```
composite = 0.40 * max_expansion
          + 0.30 * weighted_avg(relevance * expansion)
          + 0.15 * flag_bonus
          + 0.15 * time_weight
```

Where:
- **max_expansion** (40%): Highest `expansion_score` across all relevant extractions
- **weighted_avg** (30%): `sum(relevance * expansion) / sum(relevance)` for chunks above the relevance threshold (0.3)
- **flag_bonus** (15%): 0.05 per signal flag detected (CAPEX, build-to-suit, last-mile) — max 0.15
- **time_bonus** (15%): Weight from `TIME_WEIGHTS` dict based on best time horizon (immediate=1.0, near_term=0.8, medium_term=0.5, long_term=0.3, unspecified=0.2)

Chunks with `warehouse_relevance < 0.3` (RELEVANCE_THRESHOLD) are excluded from the expansion and weighted average calculations. When multiple chunks are scored, flags and time horizons are aggregated with union/max semantics.

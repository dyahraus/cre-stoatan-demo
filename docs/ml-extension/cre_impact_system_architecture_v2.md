# CRE Impact Scoring System — Architecture Design v2

## 1. Problem Statement

Given a corpus of earnings call transcripts, produce a **geographic impact score** representing the projected quarterly movement in commercial real estate (CRE) market value for a target region and its sub-regions.

- **Input**: Raw earnings call transcripts (text)
- **Output**: Impact score per (region, quarter, horizon) tuple
- **Label data**: CoStar market-level CRE data, Q1 2010 – Q4 2021 (48 quarters)
- **Granularity**: CoStar submarkets (Midwest), with extension path to zip and building level

---

## 2. Recommended Approach: Hybrid (LLM Feature Extraction → Supervised Prediction Head)

### Why Hybrid?

| Approach | Strengths | Weaknesses |
|---|---|---|
| Full custom NN | Full control, no API costs | Insufficient label volume for end-to-end text→score; massive engineering lift |
| Pure LLM prompting | Rich semantic extraction | No calibration to your label distribution; non-deterministic; expensive at scale |
| **Hybrid** | LLM handles language understanding; supervised head learns the mapping to your labels | Moderate complexity; requires feature engineering decisions |

The hybrid decouples two hard problems: (1) understanding what an earnings call *says* about CRE markets, and (2) mapping that understanding to actual market movements. An LLM solves (1); a trained model solves (2).

### On Model Complexity

Use the linear baseline (Ridge/ElasticNet) as a **diagnostic floor check**, not a ceiling. If linear models find zero signal, investigate features and labels before adding complexity. However, nonlinear feature interactions (e.g., positive sentiment × high capex × low vacancy = strong signal, even when each alone is weak) are real and expected in this domain. Gradient-boosted trees and neural nets can discover these automatically.

---

## 3. Core Entity Model

The system is built around five interconnected entity types that allow full traceability from raw language to market impact.

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│   COMPANY   │──has──▶│   PERSON    │       │   REGION    │
│             │       │  (speaker)  │       │             │
│ ticker      │       │ name        │       │ region_id   │
│ sector      │       │ role (CEO,  │       │ name        │
│ geo_exposure│       │  CFO, etc.) │       │ level (mkt, │
│ market_cap  │       │ company_id  │       │  sub, zip)  │
│ cre_segments│       └─────────────┘       │ parent_id   │
└──────┬──────┘                             │ costar_id   │
       │                                    └──────┬──────┘
       │ files                                     │
       ▼                                           │
┌──────────────────┐                               │
│ EARNINGS REPORT  │                               │
│                  │       ┌─────────────┐         │
│ report_id        │──opt──▶│   EVENT     │◀────────┘
│ company_id       │       │             │
│ fiscal_quarter   │       │ event_id    │
│ call_date        │       │ type (sale, │
│ transcript_text  │       │  lease, dev,│
│ chunks[]         │       │  default)   │
│ extracted_signals│       │ date        │
│                  │       │ region_id   │
│                  │       │ company_ids │
│                  │       │ people_ids  │
│                  │       │ value       │
│                  │       │ verified    │
└──────────────────┘       └─────────────┘
```

### Entity Relationships

- **Company → Region**: Many-to-many. A company has geographic exposure across multiple regions (weighted by portfolio allocation).
- **Earnings Report → Event**: Optional many-to-many. An earnings call may reference zero or many verifiable events. Many calls will have no linked events (nothing notable discussed).
- **Event → Region**: Many-to-one (or many-to-many if an event spans regions). Every event is geolocated.
- **Event → Company**: Many-to-many. A building sale involves a buyer and seller, both companies.
- **Event → Person**: Many-to-many. Key individuals involved.
- **Region → Region**: Self-referential hierarchy. Market → submarket → zip → building (future).

### Event Types

Events are **verifiable, real-world occurrences**:
- Building/portfolio sales (with price, cap rate, buyer, seller)
- Lease signings (tenant, sq ft, term, rate)
- Development starts / completions
- Loan originations / defaults / refinancings
- Tenant bankruptcies or expansions
- Zoning / regulatory changes

Events serve two purposes:
1. **Ground truth anchoring** — connect language in calls to things that actually happened
2. **Feature enrichment** — event density/type per region is itself a predictive signal

---

## 4. Data & Label Tiers

### Tier 1: MVP (Current Build)
- **Labels**: CoStar market-level aggregated data
- **Geography**: CoStar-predefined submarkets, Midwest focus
- **Granularity**: Submarket × quarter
- **Segmentation**: State batches divided into quarters, or CoStar submarket definitions

### Tier 2: Enhanced Geographic Resolution
- **Labels**: CoStar data at finer granularity
- **Geography**: Zip code level segmentation
- **Addition**: Dynamic region selection (user picks a region, system computes on the fly)
- **Challenge**: Label sparsity — fewer transactions per zip per quarter means noisier labels
- **Mitigation**: Hierarchical smoothing (borrow strength from parent region)

### Tier 3: Private Data Integration (Production)
- **Labels**: Client's actual realized transaction data at the building level
- **Geography**: Custom regions defined by client portfolio
- **Advantage**: Building-level price changes, not CoStar's aggregated estimates
- **Architecture implication**: The system must support pluggable label sources — the prediction head retrains on the client's data while the LLM feature extraction layer remains shared
- **Enrichment**: Combine private building-level data with macro CoStar trends for the region

### Design Principle for Tier Progression

```
The LLM feature extraction pipeline (Stage 1–2) is label-agnostic.
It produces the same feature matrix regardless of label source.

Only the prediction head (Stage 3) changes per tier/client.

This means:
  ┌────────────────────────────────┐
  │  SHARED across all tiers:      │
  │  - Transcript ingestion        │
  │  - LLM extraction prompts      │
  │  - Entity model + event graph  │
  │  - Feature aggregation logic   │
  │  - Embedding generation        │
  └────────────────────────────────┘
  ┌────────────────────────────────┐
  │  PER-TIER / PER-CLIENT:        │
  │  - Label definition + formula  │
  │  - Geographic taxonomy mapping │
  │  - Prediction head weights     │
  │  - Region aggregation rules    │
  └────────────────────────────────┘
```

---

## 5. End-to-End Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA INGESTION                               │
│  Earnings Call Transcripts → Cleaning → Chunking → Metadata Tags    │
│  Events → Verification → Geolocation → Entity Linking              │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    STAGE 1: LLM FEATURE EXTRACTION                  │
│                                                                     │
│  For each transcript chunk:                                         │
│    ┌──────────────────────────────────────────────────────────┐     │
│    │ A. Structured Signal Extraction (prompted)               │     │
│    │    - CRE sentiment polarity + intensity                  │     │
│    │    - Geographic mentions → canonical region mapping       │     │
│    │    - Forward-looking vs. backward-looking classification  │     │
│    │    - Sector signals (office, industrial, retail, etc.)    │     │
│    │    - Capex / investment intention signals                 │     │
│    │    - Risk/uncertainty language detection                  │     │
│    │    - Event extraction (link to known events or flag new)  │     │
│    └──────────────────────────────────────────────────────────┘     │
│    ┌──────────────────────────────────────────────────────────┐     │
│    │ B. Embedding Generation                                  │     │
│    │    - Dense vector per chunk (for downstream model input) │     │
│    │    - Candidate models: text-embedding-3-large, or        │     │
│    │      fine-tuned sentence-transformers                    │     │
│    └──────────────────────────────────────────────────────────┘     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 STAGE 2: AGGREGATION & FEATURE MATRIX                │
│                                                                     │
│  Group extracted features by (region, quarter):                     │
│    - Aggregate sentiment scores (mean, weighted mean, extremes)     │
│    - Count of forward-looking CRE-relevant mentions                 │
│    - Sector-weighted signal composites                              │
│    - Embedding centroid per (region, quarter)                       │
│    - Transcript volume / coverage density                           │
│    - Event density and type distribution per region                 │
│    - Optional: delta features (change from prior quarter)           │
│                                                                     │
│  Output: Feature matrix X of shape (n_regions × n_quarters, d)     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│              STAGE 3: MULTI-HORIZON PREDICTION HEADS                 │
│                                                                     │
│  Separate models per forecast horizon:                              │
│                                                                     │
│    Model_h1: X_t → ŷ_{t+1}  (1-quarter ahead)                     │
│    Model_h2: X_t → ŷ_{t+2}  (2-quarters ahead)                    │
│    Model_h3: X_t → ŷ_{t+3}  (3-quarters ahead)                    │
│    Model_h4: X_t → ŷ_{t+4}  (4-quarters ahead / 1 year)           │
│                                                                     │
│  Each model learns its own feature importances:                     │
│    - h1 may weight recent sentiment + event signals heavily         │
│    - h4 may weight capex pipeline + construction signals more       │
│                                                                     │
│  Architecture per horizon (complexity ladder):                      │
│    1. Ridge / ElasticNet (diagnostic baseline)                      │
│    2. XGBoost / LightGBM (likely best given sample size)            │
│    3. Shallow MLP (if nonlinear embedding interactions help)        │
│                                                                     │
│  Validation: Expanding-window time-series CV per horizon            │
│              (shifted forward by h quarters for each horizon)       │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│              STAGE 4: ENSEMBLE & SCORING OUTPUT                      │
│                                                                     │
│  Horizon-Weighted Ensemble:                                         │
│    - Each horizon model produces a score + confidence               │
│    - Meta-learner (or simple weighted average) combines horizons    │
│    - Weights learned from held-out performance: which model is      │
│      most accurate for which region types / market conditions?      │
│                                                                     │
│  Output per (region, quarter):                                      │
│    - Composite impact score (weighted across horizons)              │
│    - Per-horizon breakdown                                          │
│    - Confidence interval / uncertainty band                         │
│    - Attribution: which transcripts, events, sectors drove score    │
│    - Sub-region disaggregation (parent score → child estimates)     │
│                                                                     │
│  Continuous Update:                                                 │
│    - As new transcripts arrive, features update                     │
│    - Horizon models re-score with updated features                  │
│    - Ensemble weights can be periodically recalibrated              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 6. Multi-Horizon Model Design

### Separate Models per Horizon

Training **separate models per horizon** (rather than a single model with horizon as a feature) is preferred here because:

1. **Feature importance shifts with horizon**: Near-term predictions lean on sentiment momentum, recent events, and earnings tone. Longer-term predictions lean on capex pipelines, construction starts, and structural supply/demand signals. Separate models let each horizon learn its own weights naturally.

2. **Different optimal complexity**: The 1-quarter model might work well as a boosted tree on structured features. The 4-quarter model might benefit more from embedding-derived features that capture harder-to-quantify structural narratives.

3. **Independent evaluation**: You can see exactly which horizons the system is good at. Maybe it's excellent at t+1 and useless at t+4 — that's important to know and communicate to clients.

### Ensemble Layer

```
For a given (region, quarter), the final composite score:

  score_composite = Σ_h  w_h × score_h

Where:
  w_h = weight for horizon h, learned from validation performance
  score_h = prediction from Model_h

Weight learning options:
  (a) Static: w_h proportional to 1/RMSE_h on validation set
  (b) Conditional: w_h depends on market regime (e.g., volatile vs. stable periods)
  (c) Stacked: a meta-model takes [score_h1, score_h2, ...] as input and predicts y

Start with (a), upgrade to (c) if you have enough data.
```

### Horizon-Specific Validation

Each horizon has its own expanding-window CV, shifted appropriately:

```
Model_h1 (1-quarter ahead):
  Fold 1: Train on features X_{Q1'10..Q4'15}, test prediction of y_{Q1'16..Q4'16}

Model_h2 (2-quarters ahead):
  Fold 1: Train on features X_{Q1'10..Q3'15}, test prediction of y_{Q1'16..Q4'16}
  (features are from 2 quarters prior to the predicted quarter)

Model_h4 (4-quarters ahead):
  Fold 1: Train on features X_{Q1'10..Q4'14}, test prediction of y_{Q1'16..Q4'16}
  (features are from 4 quarters prior — the model must predict a year out)
```

Note: longer horizons have fewer effective training samples because more quarters are consumed by the lag. This is a real constraint — h4 loses 4 quarters of training data relative to h1.

---

## 7. Data Schema (Detailed)

### 7.1 Companies

```
companies
├── company_id          (PK, uuid)
├── ticker              (str, nullable — not all CRE firms are public)
├── name                (str)
├── sector              (enum: REIT_office, REIT_industrial, REIT_retail,
│                              REIT_residential, REIT_diversified,
│                              bank, insurance, developer, broker, other)
├── cre_segments[]      (array of {segment_type, pct_revenue})
├── market_cap          (float, nullable)
├── created_at          (timestamp)
└── updated_at          (timestamp)

company_region_exposure
├── company_id          (FK → companies)
├── region_id           (FK → regions)
├── exposure_weight     (float, 0–1, sums to 1.0 per company)
├── source              (enum: 10k_filing, manual, llm_extracted)
└── as_of_date          (date)
```

### 7.2 People

```
people
├── person_id           (PK, uuid)
├── name                (str)
├── current_company_id  (FK → companies, nullable)
├── current_role        (str)
└── roles_history[]     (array of {company_id, role, start_date, end_date})
```

### 7.3 Regions

```
regions
├── region_id           (PK, uuid)
├── name                (str)
├── level               (enum: national, state, market, submarket, zip, building)
├── parent_region_id    (FK → regions, nullable — self-referential hierarchy)
├── costar_id           (str, nullable — maps to CoStar's taxonomy)
├── geometry            (GeoJSON or WKT, nullable — for zip/building level)
├── state               (str)
└── metadata            (jsonb — population, sq_ft_inventory, etc.)

Region Hierarchy Example:
  US (national)
    └── Illinois (state)
        └── Chicago (market)
            ├── Chicago CBD (submarket, costar_id: "CHI_CBD")
            ├── O'Hare Corridor (submarket, costar_id: "CHI_OHR")
            ├── Chicago South Suburbs (submarket)
            │   ├── 60601 (zip, Tier 2+)
            │   │   └── 233 S Wacker Dr (building, Tier 3)
            ...
```

### 7.4 Earnings Reports

```
earnings_reports
├── report_id           (PK, uuid)
├── company_id          (FK → companies)
├── fiscal_year         (int)
├── fiscal_quarter      (int, 1–4)
├── call_date           (date)
├── transcript_raw      (text)
├── transcript_source   (enum: factset, capital_iq, seeking_alpha, sec_filing)
├── processing_status   (enum: raw, chunked, extracted, verified)
├── created_at          (timestamp)
└── updated_at          (timestamp)

report_chunks
├── chunk_id            (PK, uuid)
├── report_id           (FK → earnings_reports)
├── chunk_index         (int — position in transcript)
├── text                (text)
├── section_type        (enum: prepared_remarks, qa_question, qa_answer, other)
├── speaker_person_id   (FK → people, nullable)
├── speaker_role        (str — "CEO", "Analyst", etc.)
├── token_count         (int)
└── extraction_status   (enum: pending, extracted, failed)

chunk_extractions
├── extraction_id       (PK, uuid)
├── chunk_id            (FK → report_chunks)
├── model_used          (str — "claude-sonnet-4-5-20250514", etc.)
├── extraction_version  (str — prompt version tracking)
├── cre_relevance       (float, 0–1)
├── sentiment_polarity  (float, -1 to 1)
├── sentiment_intensity (enum: none, mild, moderate, strong)
├── temporal_orientation(enum: backward, current, forward)
├── sectors[]           (array of enum: office, industrial, retail, ...)
├── geographic_mentions[](array of {region_id, confidence})
├── signals             (jsonb — capex, demand, vacancy, rent, construction)
├── raw_llm_output      (jsonb — full extraction payload for debugging)
├── embedding           (vector — dense embedding of chunk)
├── created_at          (timestamp)
└── event_ids[]         (array of FK → events, extracted mentions)
```

### 7.5 Events

```
events
├── event_id            (PK, uuid)
├── event_type          (enum: sale, lease, development_start, development_complete,
│                              loan_origination, loan_default, refinancing,
│                              tenant_bankruptcy, tenant_expansion,
│                              regulatory_change, other)
├── date                (date)
├── region_id           (FK → regions)
├── description         (text)
├── value               (float, nullable — transaction price, lease value, etc.)
├── value_unit          (enum: usd, usd_per_sqft, cap_rate, etc.)
├── sq_ft               (float, nullable)
├── verified            (boolean — has this been confirmed from public records?)
├── verification_source (str, nullable)
├── property_type       (enum: office, industrial, retail, multifamily, other)
├── created_at          (timestamp)
└── updated_at          (timestamp)

event_companies
├── event_id            (FK → events)
├── company_id          (FK → companies)
└── role                (enum: buyer, seller, tenant, landlord, lender, borrower,
                               developer, broker)

event_people
├── event_id            (FK → events)
├── person_id           (FK → people)
└── role                (str)

report_events (the optional link between earnings reports and events)
├── report_id           (FK → earnings_reports)
├── event_id            (FK → events)
├── mention_type        (enum: direct_reference, implied, analyst_question)
├── chunk_id            (FK → report_chunks, nullable — which chunk mentions it)
└── confidence          (float, 0–1)
```

### 7.6 Labels (Tier-Aware)

```
cre_labels
├── label_id            (PK, uuid)
├── region_id           (FK → regions)
├── quarter             (str — "2010Q1")
├── year                (int)
├── quarter_num         (int, 1–4)
├── label_source        (enum: costar_market, costar_submarket, private_client)
├── client_id           (FK, nullable — for Tier 3 private data)
├── raw_value           (float — the raw CRE market value metric)
├── metric_type         (str — "price_per_sqft", "total_value_index", etc.)
├── computed_label      (float, nullable — the transformed target: log return, z-score, etc.)
├── label_formula       (str — documents which transformation was applied)
└── updated_at          (timestamp)
```

### 7.7 Feature Matrix (Materialized)

```
feature_matrix
├── feature_row_id      (PK, uuid)
├── region_id           (FK → regions)
├── quarter             (str — "2010Q1")
├── feature_version     (str — tracks extraction/aggregation version)
├── structured_features (jsonb — aggregated sentiment, event counts, etc.)
├── embedding_centroid  (vector)
├── embedding_spread    (float)
├── transcript_count    (int)
├── unique_companies    (int)
├── event_density       (float — events per unit time in this region)
├── computed_at         (timestamp)
└── label_id            (FK → cre_labels, nullable — joined for convenience)
```

---

## 8. Stage-by-Stage Design Details

### 8.1 Data Ingestion

**Transcript Processing**
- Parse raw transcripts into structured sections: prepared remarks vs. Q&A
- Chunk into semantically coherent segments (~500–1000 tokens per chunk)
- Tag each chunk with metadata: company ticker, date, section type, speaker role

**Geographic Mapping**
- Build a canonical geography taxonomy using CoStar submarket definitions
- Map companies to primary/secondary geographic exposures (weighted)
- Company-region mapping can be semi-automated from 10-K filings via LLM extraction, validated manually

**Event Ingestion**
- Ingest verifiable events from CoStar, public records, news feeds
- Geolocate and entity-link each event
- Events enter the system independently from earnings reports
- During LLM extraction, attempt to link transcript mentions to known events

**Temporal Alignment**
- Map each transcript to the quarter it describes (not the filing date)
- Forward-looking statements should be flagged with temporal_orientation and mapped to t+1 or t+2 as features

### 8.2 LLM Feature Extraction

Two parallel extraction paths per chunk:

**Path A: Structured Extraction (Prompted)**

Use a prompted LLM call per chunk to extract a structured JSON payload:

```json
{
  "cre_relevance": 0.85,
  "sentiment": {
    "polarity": 0.3,
    "intensity": "moderate",
    "direction": "positive"
  },
  "geographic_mentions": [
    {"region": "US_Southeast", "confidence": 0.9},
    {"region": "US_Midwest", "confidence": 0.6}
  ],
  "temporal_orientation": "forward_looking",
  "sectors": ["industrial", "logistics"],
  "signals": {
    "capex_expansion": true,
    "demand_strength": "increasing",
    "vacancy_mention": false,
    "rent_pressure": "upward",
    "construction_pipeline": "moderate"
  },
  "event_references": [
    {
      "description": "Sale of 233 S Wacker portfolio",
      "matched_event_id": "evt_abc123",
      "match_confidence": 0.92
    }
  ]
}
```

**Path B: Embedding Generation**

Dense embeddings per chunk for latent features the structured extraction might miss.

### 8.3 Aggregation & Feature Matrix

Group by (region, quarter), aggregate structured features, compute embedding centroids, add event-derived features (event density, type distribution, total transaction volume).

### 8.4 Multi-Horizon Prediction Heads

See Section 6 for full design.

---

## 9. Where Fine-Tuning Fits

Fine-tuning makes sense at two specific points if baseline performance is insufficient:

**Fine-tuning point 1: Embedding model**
- Contrastive fine-tuning on (chunk_text, cre_relevance_label) pairs
- Goal: make the embedding space more discriminative for CRE-relevant language

**Fine-tuning point 2: Structured extraction model**
- Fine-tune a smaller model (e.g., Llama 3 8B, Mistral 7B) to replicate your prompted extraction schema
- Goal: reduce inference cost at scale, improve consistency

**When NOT to fine-tune:**
- Don't fine-tune end-to-end (transcript → score) unless you have 10,000+ labeled examples
- Don't fine-tune the embedding model before establishing that embeddings add value over structured features alone

---

## 10. Key Remaining Decisions

### 10.1 Label Formula (Highest Priority)
- Which CoStar metric specifically? (Market-level price index, value-weighted return, rent growth, cap rate change?)
- Transformation: log return, percent change, z-score, rank percentile?
- Recommendation: start with **log returns** for training, translate to percent change for client presentation

### 10.2 Transcript Corpus Scope
- Which companies' earnings calls? (REITs, banks, developers, brokers, all S&P 500?)
- How many transcripts per quarter expected?
- Source: FactSet, S&P Capital IQ, Seeking Alpha, SEC EDGAR?

### 10.3 MVP Geographic Scope
- How many CoStar submarkets in the Midwest? (This determines effective sample size: N_submarkets × 48 quarters)
- Which state batches for initial build?

---

## 11. Suggested Build Order

```
Phase 1 — Foundation (Weeks 1–3)
  ├── Finalize label formula on CoStar data
  ├── Build region hierarchy (CoStar submarkets → taxonomy)
  ├── Design and implement entity model (DB schema)
  ├── Set up transcript ingestion pipeline
  └── Ingest initial event dataset

Phase 2 — Feature Extraction (Weeks 3–6)
  ├── Design and test extraction prompt on sample transcripts
  ├── Run structured extraction across full corpus
  ├── Generate embeddings across full corpus
  ├── Build aggregation pipeline → feature matrix
  └── Event linking: connect transcript mentions to events

Phase 3 — Modeling (Weeks 6–9)
  ├── Baseline: Ridge regression per horizon, structured features only
  ├── Add embedding features → compare per horizon
  ├── XGBoost with full feature set per horizon
  ├── Expanding-window time-series CV evaluation
  ├── Feature importance / SHAP analysis per horizon
  └── Initial ensemble: weighted combination across horizons

Phase 4 — Refinement (Weeks 9–12)
  ├── Error analysis: where and when does each horizon model fail?
  ├── Prompt tuning based on error patterns
  ├── Optional: embedding fine-tuning
  ├── Ensemble weight optimization
  ├── Confidence estimation / uncertainty quantification
  └── Begin Tier 2 design (zip-level, dynamic region selection)

Phase 5 — Production (Weeks 12+)
  ├── Inference pipeline for new transcripts (continuous update)
  ├── Client-facing output API + dashboard
  ├── Tier 3 architecture: pluggable label sources for private client data
  ├── Optional: fine-tune smaller extraction model (cost reduction)
  └── Monitoring, drift detection, model retraining triggers
```

---

## 12. Tech Stack Recommendations

| Component | Recommended | Rationale |
|---|---|---|
| Database | PostgreSQL + pgvector | Relational for entities, pgvector for embeddings |
| Transcript parsing | Python + custom regex / spaCy | Earnings calls have predictable structure |
| LLM extraction | Claude API (Sonnet for throughput, Opus for complex chunks) | Strong structured output, JSON mode |
| Embeddings | `text-embedding-3-large` or `bge-large-en-v1.5` | Both strong; local option avoids API costs |
| Feature storage | Parquet (archival) + PostgreSQL (serving) | Columnar for analysis, relational for API |
| Modeling | scikit-learn → XGBoost → PyTorch (as needed) | Complexity ladder |
| Experiment tracking | MLflow or Weights & Biases | Track feature sets, hyperparams, CV scores |
| Orchestration | Prefect or Dagster | Pipeline DAGs, retries, scheduling |
| API | FastAPI | Async, type-safe, auto-docs |
| Geo | PostGIS extension (for Tier 2+ zip/building geospatial queries) | Spatial indexing, containment queries |

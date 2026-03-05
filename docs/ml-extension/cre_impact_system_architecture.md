# CRE Impact Scoring System — Architecture Design

## 1. Problem Statement

Given a corpus of earnings call transcripts, produce a **geographic impact score** representing the projected quarterly movement in commercial real estate (CRE) market value for a target region and its sub-regions.

- **Input**: Raw earnings call transcripts (text)
- **Output**: Impact score per (region, quarter) pair
- **Label data**: Continuous CRE market value observations, Q1 2010 – Q4 2021 (48 quarters)
- **Granularity**: Regional and sub-regional

---

## 2. Recommended Approach: Hybrid (LLM Feature Extraction → Supervised Prediction Head)

### Why Hybrid?

| Approach | Strengths | Weaknesses |
|---|---|---|
| Full custom NN | Full control, no API costs | Insufficient label volume for end-to-end text→score; massive engineering lift |
| Pure LLM prompting | Rich semantic extraction | No calibration to your label distribution; non-deterministic; expensive at scale |
| **Hybrid** | LLM handles language understanding; supervised head learns the mapping to your labels | Moderate complexity; requires feature engineering decisions |

The hybrid decouples two hard problems: (1) understanding what an earnings call *says* about CRE markets, and (2) mapping that understanding to actual market movements. An LLM solves (1); a trained model solves (2).

---

## 3. End-to-End Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA INGESTION                               │
│  Earnings Call Transcripts → Cleaning → Chunking → Metadata Tags    │
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
│    - Optional: delta features (change from prior quarter)           │
│                                                                     │
│  Output: Feature matrix X of shape (n_regions × n_quarters, d)     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    STAGE 3: PREDICTION HEAD                          │
│                                                                     │
│  Supervised model: X → ŷ (predicted CRE market movement)           │
│                                                                     │
│  Candidate architectures (in order of complexity):                  │
│    1. Ridge / ElasticNet regression (strong baseline)               │
│    2. Gradient-boosted trees (XGBoost / LightGBM)                  │
│    3. Shallow MLP (2–3 layers) with dropout                        │
│    4. Temporal model (LSTM or Transformer) if sequential            │
│       signal across quarters is important                           │
│                                                                     │
│  Label: y = f(CRE market value) at quarter t                       │
│         (formula TBD — likely % change or z-scored delta)           │
│                                                                     │
│  Validation: Time-series cross-validation (expanding window)        │
│              NOT random split — data is temporally ordered           │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     STAGE 4: SCORING & OUTPUT                       │
│                                                                     │
│  For each (region, quarter):                                        │
│    - Point estimate of CRE impact score                             │
│    - Confidence interval / uncertainty estimate                     │
│    - Decomposition: which transcripts/sectors drove the score       │
│    - Sub-region rollup or disaggregation                            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Stage-by-Stage Design Details

### 4.1 Data Ingestion

**Transcript Processing**
- Parse raw transcripts into structured sections: prepared remarks vs. Q&A
- Chunk into semantically coherent segments (~500–1000 tokens per chunk)
- Tag each chunk with metadata: company ticker, date, section type, speaker role (CEO, CFO, analyst)

**Geographic Mapping**
- Build a canonical geography taxonomy: regions → sub-regions
- Map companies to primary/secondary geographic exposures (e.g., Simon Property Group → US retail CRE, heavy Southeast/Midwest)
- This mapping can be partially automated via LLM extraction from 10-K filings, but will need a curated lookup table

**Temporal Alignment**
- Map each transcript to the quarter it describes (not the filing date — earnings calls often discuss the prior quarter plus forward guidance)
- Forward-looking statements should map to t+1 or t+2

### 4.2 LLM Feature Extraction

This is the core value-add of the hybrid approach. Two parallel extraction paths:

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
  }
}
```

Key prompt engineering consideration: the schema should be rigid and well-defined so outputs are consistent across thousands of chunks. Use structured output / JSON mode.

**Path B: Embedding Generation**

Generate dense embeddings per chunk for features that are hard to enumerate explicitly. These capture latent signals the structured extraction might miss.

Candidate embedding models:
- OpenAI `text-embedding-3-large` (1536 or 3072 dims)
- Sentence-transformers (e.g., `all-MiniLM-L6-v2` for speed, `bge-large-en-v1.5` for quality)
- Fine-tuned embeddings (later optimization — train contrastively on CRE-relevant vs. irrelevant chunks)

### 4.3 Aggregation & Feature Matrix

This is where company-level, chunk-level signals become region-quarter observations.

**Aggregation strategy:**

```
For each (region r, quarter t):
    1. Collect all chunks C_{r,t} where:
       - company is geographically mapped to region r
       - transcript is temporally aligned to quarter t
    
    2. Structured features:
       - mean_sentiment     = mean([c.sentiment.polarity for c in C_{r,t}])
       - weighted_sentiment  = weighted by c.cre_relevance
       - fwd_looking_count  = count where temporal_orientation == "forward_looking"
       - sector_signals     = per-sector aggregated demand/supply indicators
       - capex_signal       = fraction of chunks with capex_expansion == true
    
    3. Embedding features:
       - embedding_centroid = mean([embed(c) for c in C_{r,t}])
       - embedding_spread   = std of chunk embeddings (captures disagreement)
    
    4. Meta features:
       - transcript_count   = |C_{r,t}|  (coverage proxy)
       - unique_companies   = number of distinct companies
    
    5. Temporal features (optional but recommended):
       - delta_sentiment    = mean_sentiment_t - mean_sentiment_{t-1}
       - momentum           = rolling 2-quarter average of sentiment
```

**Dimensionality considerations:**
- Structured features: ~15–30 dimensions
- Embedding centroid: 256–1536 dimensions (consider PCA reduction)
- Total feature vector per (region, quarter): ~50–300 dimensions after reduction

### 4.4 Prediction Head

**Label definition (TBD — your call, but here are options):**

| Label Formula | Pros | Cons |
|---|---|---|
| `pct_change = (V_t - V_{t-1}) / V_{t-1}` | Intuitive, scale-free | Sensitive to base effects |
| `log_return = ln(V_t / V_{t-1})` | Symmetric, additive across time | Less intuitive to stakeholders |
| `z_score = (V_t - mean) / std` | Normalized, comparable across regions | Loses absolute magnitude |
| `rank_percentile` per quarter | Robust to outliers | Loses magnitude information |

Recommendation: start with **log returns** for model training (better statistical properties), translate to percent change for presentation.

**Model selection guidance:**

Given ~48 quarters × N regions (say 10–50 regions = 480–2400 samples):

1. **Start with Ridge/ElasticNet** — this is your sanity-check baseline. If linear features from the LLM extraction can't predict at all, deeper models won't help either.

2. **Gradient-boosted trees (XGBoost)** — handles mixed feature types well, automatic feature interaction, built-in regularization. Likely your best performer given sample size.

3. **Shallow MLP** — only if you want to learn nonlinear combinations of the embedding features specifically. Use heavy dropout and early stopping.

4. **Temporal model** — only pursue if you find strong autocorrelation in residuals from the above models. A simple LSTM or 1D-conv over the quarterly sequence per region could capture momentum effects.

**Validation protocol (critical):**

```
DO NOT use random train/test splits.

Use expanding-window time-series CV:
  Fold 1: Train Q1'10–Q4'15, Test Q1'16–Q4'16
  Fold 2: Train Q1'10–Q4'16, Test Q1'17–Q4'17
  Fold 3: Train Q1'10–Q4'17, Test Q1'18–Q4'18
  Fold 4: Train Q1'10–Q4'18, Test Q1'19–Q4'19
  Fold 5: Train Q1'10–Q4'19, Test Q1'20–Q4'20
  Fold 6: Train Q1'10–Q4'20, Test Q1'21–Q4'21
```

This respects temporal ordering and prevents look-ahead bias.

---

## 5. Where Fine-Tuning Fits

Fine-tuning makes sense at two specific points if baseline performance is insufficient:

**Fine-tuning point 1: Embedding model**
- Contrastive fine-tuning on (chunk_text, cre_relevance_label) pairs
- Goal: make the embedding space more discriminative for CRE-relevant language
- Requires: a few thousand labeled chunk pairs (can be generated via the structured extraction as weak labels)

**Fine-tuning point 2: Structured extraction model**
- Fine-tune a smaller model (e.g., Llama 3 8B, Mistral 7B) to replicate your prompted extraction schema
- Goal: reduce inference cost at scale, improve consistency
- Requires: a gold-standard set of ~500–1000 manually verified extraction outputs
- This is an optimization step — do it after the pipeline is validated with prompted extraction

**When NOT to fine-tune:**
- Don't fine-tune end-to-end (transcript → score) unless you have 10,000+ labeled examples
- Don't fine-tune the embedding model before establishing that embeddings are actually predictive features in your downstream model

---

## 6. Key Open Questions to Resolve

### 6.1 Label Construction (Highest Priority)
- What is the CRE market value measure? (NCREIF NPI, Green Street CPPI, CoStar CCRSI, cap rate derived?)
- What geographic granularity does the label data support?
- How will you handle regions where label data is sparse?
- Are you predicting level, change, or direction?

### 6.2 Geographic Taxonomy
- How many regions/sub-regions?
- How do you handle companies with multi-region exposure? (proportional allocation vs. primary region?)
- Metro-level vs. state-level vs. Census division?

### 6.3 Transcript Corpus
- Which companies' earnings calls? (REITs only? Banks? Construction? All S&P 500?)
- How many transcripts per quarter do you expect?
- Source: FactSet, S&P Capital IQ, Seeking Alpha, direct SEC filings?

### 6.4 Temporal Alignment
- Lag structure: does Q3 earnings language predict Q3 CRE movement (contemporaneous) or Q4 (leading)?
- Should you model multiple lead/lag windows and let the model learn the optimal one?

---

## 7. Suggested Build Order

```
Phase 1 — Foundation (Weeks 1–3)
  ├── Finalize label construction formula
  ├── Build geographic taxonomy + company-to-region mapping
  ├── Set up transcript ingestion pipeline (parsing, chunking, metadata)
  └── Establish data storage schema

Phase 2 — Feature Extraction (Weeks 3–5)
  ├── Design and test extraction prompt on sample transcripts
  ├── Run structured extraction across full corpus
  ├── Generate embeddings across full corpus
  └── Build aggregation pipeline → feature matrix

Phase 3 — Modeling (Weeks 5–7)
  ├── Baseline: Ridge regression on structured features only
  ├── Add embedding features → compare
  ├── XGBoost with full feature set
  ├── Time-series CV evaluation framework
  └── Feature importance / SHAP analysis

Phase 4 — Refinement (Weeks 7–10)
  ├── Error analysis: where does the model fail?
  ├── Prompt tuning based on error patterns
  ├── Optional: embedding fine-tuning
  ├── Optional: temporal modeling layer
  └── Confidence estimation / uncertainty quantification

Phase 5 — Production (Weeks 10+)
  ├── Inference pipeline for new transcripts
  ├── Optional: fine-tune smaller model for extraction (cost reduction)
  ├── Monitoring and drift detection
  └── Output API / dashboard
```

---

## 8. Tech Stack Recommendations

| Component | Recommended | Rationale |
|---|---|---|
| Transcript parsing | Python + custom regex / spaCy | Earnings calls have predictable structure |
| LLM extraction | Claude API (Sonnet for throughput, Opus for quality) | Strong structured output, JSON mode |
| Embeddings | OpenAI `text-embedding-3-large` or `bge-large-en-v1.5` | Both strong; local option avoids API costs |
| Feature storage | Parquet files or DuckDB | Columnar, fast, no infra overhead |
| Modeling | scikit-learn → XGBoost → PyTorch (as needed) | Complexity ladder |
| Experiment tracking | MLflow or Weights & Biases | Track feature sets, hyperparams, CV scores |
| Orchestration | Prefect or simple Makefile | Pipeline reproducibility |

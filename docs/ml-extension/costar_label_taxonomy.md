# CoStar Label Taxonomy: Primitive vs. Derived

## The Problem

If we train separate prediction heads on every CoStar column, we risk:
1. **Redundancy** — predicting the same information multiple times under different names
2. **Inconsistency** — predicted ratio ≠ ratio of predicted components
3. **Inflated signal** — composite scores double-count correlated predictions

We need to identify which columns are **primitive** (independently measured, irreducible)
and which are **derived** (mathematically computable from other columns).

We train prediction models ONLY on primitives. Derived metrics can be computed
post-prediction from predicted primitives, ensuring internal consistency.

---

## Column-by-Column Classification

### PRIMITIVE — Train Models on These

These are independently measured, irreducible quantities that cannot be computed
from other columns in the dataset.

| # | Column | What It Measures | Category | Notes |
|---|--------|-----------------|----------|-------|
| 1 | **Vacancy Rate** | % of inventory currently unoccupied | Demand/Supply Balance | Technically = vacant_units / inventory, but CoStar measures this directly. It's the canonical demand-supply equilibrium signal. |
| 2 | **Market Asking Rent/Unit** | Current asking rent level | Pricing | The absolute price of occupancy. Fundamental to valuation. |
| 3 | **Inventory Units** | Total existing stock of units | Supply Stock | The denominator of the market. Changes slowly (only via deliveries and demolitions). |
| 4 | **Under Constr Units** | Units currently being built | Supply Pipeline | Forward-looking supply signal. Leading indicator of future inventory changes. |
| 5 | **Construction Starts** | New units entering construction this period | Supply Initiation | The earliest signal of future supply. Leads Under Constr, which leads Delivered. |
| 6 | **Net Delivered Units** | Units completed and delivered this quarter | Supply Arrival | Quarterly flow of new supply into the market. |
| 7 | **Net Absorption Units** | Net change in occupied units this quarter | Demand Flow | Quarterly demand signal: positive = demand growing, negative = shrinking. |
| 8 | **Market Sale Price/Unit** | Transaction price per unit | Capital Markets | What buyers are actually paying. Fundamental pricing signal. |
| 9 | **Market Cap Rate** | Observed capitalization rate on transactions | Capital Markets | See note below on semi-derived status. |
| 10 | **Sales Volume** | Transaction volume this quarter ($ or count) | Capital Markets / Liquidity | Measures market liquidity and investor activity. |

**Note on Cap Rate**: Cap Rate = NOI / Price. In theory it's derivable from rent and
price, but in practice CoStar reports *observed transaction cap rates* which embed
risk premia, growth expectations, and financing conditions that aren't captured by
a simple rent/price ratio. **Treat as primitive** but monitor correlation with
Rent/Unit and Sale Price/Unit — if it adds no incremental information in your models,
consider dropping it.

**Note on Vacancy Rate**: While vacancy = vacant_units / inventory_units, the
numerator (vacant_units) isn't directly in your dataset, and Vacancy Rate is
CoStar's directly measured equilibrium indicator. **Treat as primitive.**

---

### DERIVED — Do NOT Train Models on These

These are mathematically computable from the primitives above. Predict the
primitives, then compute these post-hoc for consistency.

| # | Column | Derivation | Parent Primitives |
|---|--------|-----------|-------------------|
| 1 | **Annual Rent Growth** | `= (Rent_t - Rent_{t-4}) / Rent_{t-4}` | Market Asking Rent/Unit |
| 2 | **Under Constr % of Inventory** | `= Under Constr Units / Inventory Units` | Under Constr Units, Inventory Units |
| 3 | **12 Mo Sales Vol Growth** | `= (SalesVol_12mo_t - SalesVol_12mo_{t-4}) / SalesVol_12mo_{t-4}` | Sales Volume (trailing sum + growth) |
| 4 | **12 Mo Absorp Units** | `= Σ Net Absorption Units over prior 4 quarters` | Net Absorption Units |
| 5 | **12 Mo Sales Vol** | `= Σ Sales Volume over prior 4 quarters` | Sales Volume |
| 6 | **Net Delivered Units 12 Mo** | `= Σ Net Delivered Units over prior 4 quarters` | Net Delivered Units |
| 7 | **Stabilized Vacancy** | CoStar's modeled/adjusted vacancy (smoothed or forward-looking estimate) | Vacancy Rate (adjusted) |

### Why Exclude Derived Columns

**Annual Rent Growth**: If you predict Rent/Unit at t+1 and t+2, you can compute
the growth rate directly. Training a separate model on growth risks inconsistency:
your predicted growth might not match the change between your predicted rent levels.

**Under Constr % of Inventory**: A pure ratio. If you predict both components,
compute the ratio. A model trained on the ratio might learn to predict the ratio
well while being inconsistent with the component predictions.

**12-Month Trailing Sums** (Absorption, Sales Vol, Delivered Units): These are
rolling 4-quarter sums of their quarterly counterparts. If you predict the quarterly
primitive at each horizon, sum them for the trailing figure.

**Stabilized Vacancy**: This is CoStar's *modeled* vacancy, not raw observed.
It bakes in CoStar's own assumptions. We want to predict from raw signals,
not predict CoStar's model output.

---

## Recommended Prediction Target Structure

### Primary Prediction Targets (10 Primitives × 4 Horizons = 40 Models)

```
For each primitive p ∈ {1..10}, for each horizon h ∈ {1..4}:
    Model_{p,h}: Features_t → Predicted_p_{t+h}
```

### Label Transformation per Primitive

Not all primitives should use the same label transformation. The right transform
depends on the statistical properties of each series:

| Primitive | Recommended Transform | Rationale |
|---|---|---|
| Vacancy Rate | **Level or first difference** | Bounded (0–100%), already a rate; log transform inappropriate |
| Market Asking Rent/Unit | **Log return**: `ln(Rent_t / Rent_{t-1})` | Positive, multiplicative growth; log return normalizes scale across regions |
| Inventory Units | **First difference or % change** | Large, slowly changing stock; absolute changes may matter more than % |
| Under Constr Units | **Level** | Can be zero; volatile; level prediction is most interpretable |
| Construction Starts | **Level** | Can be zero; often lumpy/discrete |
| Net Delivered Units | **Level** | Can be zero; flow variable |
| Net Absorption Units | **Level or z-score** | Can be negative; flow variable; z-score normalizes across regions |
| Market Sale Price/Unit | **Log return**: `ln(Price_t / Price_{t-1})` | Positive, multiplicative; this is closest to your "CRE market value movement" |
| Market Cap Rate | **First difference** (bps change) | Small number (4–10%); absolute bps change is standard in industry |
| Sales Volume | **Log return or z-score** | Highly volatile; log dampens extremes; z-score normalizes |

### Computing the Composite Impact Score

After predicting all 10 primitives across horizons, combine into a single
impact score per (region, quarter, horizon):

```
Impact_Score_{r,t,h} = Σ_p  w_p × Predicted_p_{r,t+h}

Where:
  w_p = weight reflecting importance of primitive p to overall CRE market health
  Predicted_p is the transformed (normalized) prediction for primitive p
```

Weight options:
  (a) Domain-expert assigned (you define what matters most)
  (b) PCA-derived (let the variance structure of the label data determine weights)
  (c) Learned (if you have an overarching "ground truth" composite, regress on it)

Recommended starting point: **Asset Value log return as the primary target**,
with the other 9 primitives as supporting predictions that feed into attribution
and decomposition.

---

## Where Does "Asset Value" Fit?

Asset Value is interesting — it's listed first in your CoStar data, and it's arguably
the single most direct measure of "CRE market value" which is what your impact
score represents.

**However, Asset Value in CoStar is itself modeled.** It's typically derived from:
  Asset Value ≈ NOI / Cap Rate ≈ f(Rent, Vacancy, Expenses, Cap Rate)

This means Asset Value is downstream of several of your other primitives. Two options:

### Option A: Treat Asset Value as the Primary Label
- Train your main models to predict Asset Value movement
- Use other primitives as *features* (contemporaneous or lagged) alongside
  transcript-derived features
- Pro: directly predicts what you care about
- Con: CoStar's Asset Value bakes in their modeling assumptions

### Option B: Treat Asset Value as a Derived Composite
- Predict the primitives (rent, vacancy, cap rate, etc.) from transcripts
- Compute Asset Value as a function of predicted primitives
- Pro: more transparent, decomposable
- Con: error propagation from multiple predicted inputs

### Recommendation: Hybrid
- **Use Asset Value log return as your primary prediction target** (Option A)
  for the composite impact score — it's the most direct measure of what clients care about
- **Also predict the 10 primitives independently** (Option B) for attribution
  and decomposition — clients want to know *why* the score moved
- Compare the two approaches: does directly predicting Asset Value outperform
  the composite of primitive predictions? This tells you something about
  whether CoStar's valuation model captures dynamics your primitives miss.

---

## Summary: What to Build

```
TRAIN prediction models on:
  ✅ Vacancy Rate
  ✅ Market Asking Rent/Unit
  ✅ Inventory Units
  ✅ Under Constr Units
  ✅ Construction Starts
  ✅ Net Delivered Units
  ✅ Net Absorption Units
  ✅ Market Sale Price/Unit
  ✅ Market Cap Rate
  ✅ Sales Volume
  ✅ Asset Value (as primary composite target)

COMPUTE post-prediction (do not train on):
  🚫 Annual Rent Growth         → derive from predicted Rent
  🚫 Under Constr % of Inventory → derive from predicted components
  🚫 12 Mo Sales Vol Growth     → derive from predicted Sales Volume
  🚫 12 Mo Absorp Units         → derive from predicted Net Absorption
  🚫 12 Mo Sales Vol            → derive from predicted Sales Volume
  🚫 Net Delivered Units 12 Mo  → derive from predicted Net Delivered
  🚫 Stabilized Vacancy         → use raw Vacancy Rate instead

Total: 11 targets × 4 horizons × N model types = model grid
```

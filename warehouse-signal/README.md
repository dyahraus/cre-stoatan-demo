# Warehouse Signal

Earnings call transcript analysis for warehouse expansion signals. Built for industrial real estate brokers who want to detect companies planning warehouse/DC expansion before deals hit the market.

## Architecture

```
Transcript Provider (FMP / EarningsCall / Mock)
        │
        ▼
┌──────────────────┐
│  Ingestion Layer  │  fetch → parse sections → chunk → store
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Signal Extract   │  LLM analyzes each chunk for warehouse signals (TODO)
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Scoring / Alerts │  Company-level expansion scores + deal radar (TODO)
└──────────────────┘
```

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Copy env template and configure
cp .env.example .env
# Edit .env with your API keys

# Initialize database + load company universe
python scripts/ingest.py --setup

# Ingest a single transcript (mock provider, no API key needed)
python scripts/ingest.py --provider mock --ticker PLD --year 2024 --quarter 3

# Ingest a full quarter for all S&P 500 companies
python scripts/ingest.py --provider mock --universe --year 2024 --quarter 4

# Backfill all available transcripts for a company
python scripts/ingest.py --provider mock --ticker AMZN --backfill

# Check database stats
python scripts/ingest.py --stats

# Run tests
pytest tests/ -v
```

## Provider-Agnostic Design

The system is designed to work with any transcript provider. Set `TRANSCRIPT_PROVIDER` in `.env`:

| Provider | Env Var | Key Feature |
|----------|---------|-------------|
| `mock` | (none needed) | Synthetic data for development |
| `fmp` | `FMP_API_KEY` | Broadest history, $149/mo |
| `earningscall` | `EARNINGSCALL_API_KEY` | Pre-segmented prepared remarks / Q&A |

To add a new provider, implement `TranscriptProvider` (see `src/warehouse_signal/providers/base.py`).

## Project Structure

```
warehouse-signal/
├── src/warehouse_signal/
│   ├── config.py              # Env-based configuration
│   ├── models/schemas.py      # Pydantic data models
│   ├── providers/
│   │   ├── base.py            # Abstract provider interface
│   │   ├── fmp.py             # Financial Modeling Prep
│   │   ├── earningscall.py    # EarningsCall.biz
│   │   └── mock.py            # Mock data for testing
│   ├── ingestion/
│   │   ├── parser.py          # Section detection + chunking
│   │   └── pipeline.py        # Fetch → parse → chunk → store
│   ├── storage/
│   │   └── sqlite.py          # SQLite backend (MVP)
│   ├── universe/
│   │   └── sp500.py           # S&P 500 company universe
│   └── analysis/              # Signal extraction (next phase)
├── scripts/
│   └── ingest.py              # CLI entry point
├── tests/
│   └── test_ingestion.py      # 11 tests covering full pipeline
└── pyproject.toml
```

## Next Steps

1. **Signal Extraction** — Claude API integration to analyze each chunk for warehouse expansion signals
2. **Scoring** — Company-level expansion scores aggregated from chunk-level signals
3. **Alerts** — Watchlist dashboard and "deal radar" filtering by geography and signal strength

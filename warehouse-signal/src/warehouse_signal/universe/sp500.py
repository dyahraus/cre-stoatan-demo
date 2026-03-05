"""S&P 500 company universe management.

For the MVP, we start with the full S&P 500 and let the LLM extraction layer
determine which transcripts actually contain warehouse/logistics signals.
This avoids prematurely narrowing the universe — retailers, manufacturers,
and food distributors often drop the most interesting logistics hints.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from warehouse_signal.models.schemas import Company, Sector

# Cache path for the company list
_CACHE_DIR = Path("data")
_CACHE_FILE = _CACHE_DIR / "sp500_companies.json"

# Sector mapping heuristic: map GICS sub-industries to our warehouse-relevant sectors
_SECTOR_KEYWORDS: dict[str, Sector] = {
    "industrial reit": Sector.REIT_INDUSTRIAL,
    "diversified reit": Sector.REIT_DIVERSIFIED,
    "specialized reit": Sector.REIT_DIVERSIFIED,
    "air freight": Sector.LOGISTICS_3PL,
    "trucking": Sector.LOGISTICS_3PL,
    "logistics": Sector.LOGISTICS_3PL,
    "internet retail": Sector.ECOMMERCE,
    "broadline retail": Sector.RETAIL,
    "general merchandise": Sector.RETAIL,
    "department store": Sector.RETAIL,
    "home improvement": Sector.RETAIL,
    "food distribut": Sector.FOOD_DISTRIBUTION,
    "food retail": Sector.FOOD_DISTRIBUTION,
    "packaged food": Sector.FOOD_DISTRIBUTION,
    "auto": Sector.AUTOMOTIVE,
    "construction": Sector.CONSTRUCTION,
    "building product": Sector.CONSTRUCTION,
    "household durable": Sector.MANUFACTURING,
    "industrial machinery": Sector.MANUFACTURING,
    "electrical equipment": Sector.MANUFACTURING,
}


def _infer_sector(industry: str) -> Sector:
    """Best-effort sector inference from GICS industry name."""
    industry_lower = industry.lower()
    for keyword, sector in _SECTOR_KEYWORDS.items():
        if keyword in industry_lower:
            return sector
    return Sector.OTHER


async def fetch_sp500_tickers() -> list[Company]:
    """Fetch S&P 500 constituents from a public data source.

    Falls back to cached data if the network call fails.
    Uses the FMP endpoint if an API key is available, otherwise falls
    back to a minimal hardcoded core list for development.
    """
    # Try to load from cache first
    if _CACHE_FILE.exists():
        data = json.loads(_CACHE_FILE.read_text())
        return [Company(**c) for c in data]

    # Try FMP's free endpoint for S&P 500 constituents
    from warehouse_signal.config import Config
    if Config.FMP_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://financialmodelingprep.com/api/v3/sp500_constituent",
                    params={"apikey": Config.FMP_API_KEY},
                )
                resp.raise_for_status()
                raw = resp.json()

                companies = []
                for item in raw:
                    sector = _infer_sector(item.get("subSector", item.get("sector", "")))
                    companies.append(
                        Company(
                            ticker=item["symbol"],
                            name=item.get("name", item["symbol"]),
                            sector=sector,
                            cik=item.get("cik"),
                        )
                    )

                # Cache it
                _CACHE_DIR.mkdir(parents=True, exist_ok=True)
                _CACHE_FILE.write_text(
                    json.dumps([c.model_dump() for c in companies], indent=2)
                )
                return companies
        except Exception:
            pass  # Fall through to hardcoded list

    # Hardcoded core list for development without API key
    return _get_core_watchlist()


def _get_core_watchlist() -> list[Company]:
    """Hardcoded core tickers for development.

    This is NOT the full S&P 500 — it's a curated set of companies
    most likely to discuss warehouse/logistics topics. Used as a fallback
    when no API key is available.
    """
    tickers = [
        # Industrial REITs
        ("PLD", "Prologis Inc", Sector.REIT_INDUSTRIAL),
        ("STAG", "STAG Industrial Inc", Sector.REIT_INDUSTRIAL),
        ("REXR", "Rexford Industrial Realty", Sector.REIT_INDUSTRIAL),
        ("EGP", "EastGroup Properties", Sector.REIT_INDUSTRIAL),
        ("FR", "First Industrial Realty Trust", Sector.REIT_INDUSTRIAL),
        # Diversified REITs with industrial
        ("DLR", "Digital Realty Trust", Sector.REIT_DIVERSIFIED),
        ("PSA", "Public Storage", Sector.REIT_DIVERSIFIED),
        # 3PL / Logistics
        ("XPO", "XPO Inc", Sector.LOGISTICS_3PL),
        ("CHRW", "C.H. Robinson Worldwide", Sector.LOGISTICS_3PL),
        ("EXPD", "Expeditors International", Sector.LOGISTICS_3PL),
        ("FDX", "FedEx Corporation", Sector.LOGISTICS_3PL),
        ("UPS", "United Parcel Service", Sector.LOGISTICS_3PL),
        # E-commerce
        ("AMZN", "Amazon.com Inc", Sector.ECOMMERCE),
        ("EBAY", "eBay Inc", Sector.ECOMMERCE),
        ("ETSY", "Etsy Inc", Sector.ECOMMERCE),
        # Retail (heavy DC users)
        ("WMT", "Walmart Inc", Sector.RETAIL),
        ("TGT", "Target Corporation", Sector.RETAIL),
        ("COST", "Costco Wholesale", Sector.RETAIL),
        ("HD", "The Home Depot", Sector.RETAIL),
        ("LOW", "Lowe's Companies", Sector.RETAIL),
        ("DG", "Dollar General", Sector.RETAIL),
        ("DLTR", "Dollar Tree", Sector.RETAIL),
        # Food distribution
        ("SYY", "Sysco Corporation", Sector.FOOD_DISTRIBUTION),
        ("USFD", "US Foods Holding", Sector.FOOD_DISTRIBUTION),
        ("KR", "The Kroger Co", Sector.FOOD_DISTRIBUTION),
        # Manufacturing / Industrial
        ("CAT", "Caterpillar Inc", Sector.MANUFACTURING),
        ("DE", "Deere & Company", Sector.MANUFACTURING),
        ("GE", "GE Aerospace", Sector.MANUFACTURING),
        # Automotive
        ("F", "Ford Motor Company", Sector.AUTOMOTIVE),
        ("GM", "General Motors", Sector.AUTOMOTIVE),
    ]
    return [
        Company(ticker=t, name=n, sector=s, sp500=True)
        for t, n, s in tickers
    ]


async def get_universe() -> list[Company]:
    """Get the current company universe, with caching."""
    return await fetch_sp500_tickers()

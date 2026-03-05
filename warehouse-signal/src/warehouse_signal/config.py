"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Central configuration. All values come from env vars with sensible defaults."""

    # Provider selection
    TRANSCRIPT_PROVIDER: str = os.getenv("TRANSCRIPT_PROVIDER", "mock")

    # API keys
    FMP_API_KEY: str = os.getenv("FMP_API_KEY", "")
    EARNINGSCALL_API_KEY: str = os.getenv("EARNINGSCALL_API_KEY", "")
    FINNHUB_API_KEY: str = os.getenv("FINNHUB_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Database
    DATABASE_PATH: Path = Path(os.getenv("DATABASE_PATH", "data/warehouse_signal.db"))

    # CORS
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:3000")

    # Polling
    POLL_INTERVAL_SECONDS: int = int(os.getenv("POLL_INTERVAL_SECONDS", "3600"))

    # LLM settings
    LLM_MODEL: str = os.getenv("LLM_MODEL", "claude-haiku-4-5-20251001")
    CHUNK_TARGET_TOKENS: int = int(os.getenv("CHUNK_TARGET_TOKENS", "800"))
    CHUNK_MAX_TOKENS: int = int(os.getenv("CHUNK_MAX_TOKENS", "1200"))

    # Analyzer settings
    ANALYZER: str = os.getenv("ANALYZER", "mock")
    EXTRACTION_VERSION: str = os.getenv("EXTRACTION_VERSION", "v1.0")
    EXTRACTION_CONCURRENCY: int = int(os.getenv("EXTRACTION_CONCURRENCY", "3"))
    EXTRACTION_MAX_TOKENS: int = int(os.getenv("EXTRACTION_MAX_TOKENS", "1024"))

    @classmethod
    def validate(cls) -> list[str]:
        """Return a list of configuration warnings/errors."""
        issues = []
        if cls.TRANSCRIPT_PROVIDER != "mock" and not cls._key_for_provider():
            issues.append(
                f"TRANSCRIPT_PROVIDER={cls.TRANSCRIPT_PROVIDER} but no API key is set. "
                f"Set {cls.TRANSCRIPT_PROVIDER.upper()}_API_KEY in your .env file."
            )
        if not cls.ANTHROPIC_API_KEY:
            issues.append("ANTHROPIC_API_KEY is not set. Signal extraction will not work.")
        return issues

    @classmethod
    def _key_for_provider(cls) -> str:
        return {
            "fmp": cls.FMP_API_KEY,
            "earningscall": cls.EARNINGSCALL_API_KEY,
            "finnhub": cls.FINNHUB_API_KEY,
            "mock": "not_needed",
        }.get(cls.TRANSCRIPT_PROVIDER, "")

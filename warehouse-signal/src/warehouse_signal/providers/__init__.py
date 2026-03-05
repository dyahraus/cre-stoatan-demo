"""Provider factory. Import and call get_provider() to get the configured provider."""

from __future__ import annotations

from warehouse_signal.config import Config
from warehouse_signal.providers.base import TranscriptProvider


def get_provider(provider_name: str | None = None) -> TranscriptProvider:
    """Instantiate the transcript provider specified by config or override.

    Usage:
        provider = get_provider()           # uses TRANSCRIPT_PROVIDER env var
        provider = get_provider("mock")     # explicit override
    """
    name = (provider_name or Config.TRANSCRIPT_PROVIDER).lower()

    if name == "fmp":
        from warehouse_signal.providers.fmp import FMPProvider
        return FMPProvider()

    elif name == "earningscall":
        from warehouse_signal.providers.earningscall import EarningsCallProvider
        return EarningsCallProvider()

    elif name == "mock":
        from warehouse_signal.providers.mock import MockProvider
        return MockProvider()

    else:
        raise ValueError(
            f"Unknown transcript provider: '{name}'. "
            f"Valid options: fmp, earningscall, mock"
        )


__all__ = ["TranscriptProvider", "get_provider"]

"""Analyzer factory. Import and call get_analyzer() to get the configured analyzer."""

from __future__ import annotations

from warehouse_signal.analysis.base import SignalAnalyzer
from warehouse_signal.config import Config


def get_analyzer(analyzer_name: str | None = None) -> SignalAnalyzer:
    """Instantiate the signal analyzer specified by config or override.

    Usage:
        analyzer = get_analyzer()            # uses ANALYZER env var
        analyzer = get_analyzer("claude")    # explicit override
    """
    name = (analyzer_name or Config.ANALYZER).lower()

    if name == "claude":
        from warehouse_signal.analysis.extractor import ClaudeAnalyzer
        return ClaudeAnalyzer()

    elif name == "mock":
        from warehouse_signal.analysis.mock import MockAnalyzer
        return MockAnalyzer()

    else:
        raise ValueError(
            f"Unknown analyzer: '{name}'. "
            f"Valid options: claude, mock"
        )


__all__ = ["SignalAnalyzer", "get_analyzer"]

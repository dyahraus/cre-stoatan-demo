"""Section + speaker boost tests."""

from __future__ import annotations

import pytest

from warehouse_signal.models.schemas import BoostConfig
from warehouse_signal.scoring.aggregator import (
    apply_boosts,
    _section_boost,
    _speaker_boost,
)


def test_default_boosts_are_neutral():
    boosts = BoostConfig()
    score, mult = apply_boosts(0.7, "prepared_remarks", "CEO", boosts)
    assert score == 0.7
    assert mult == 1.0


def test_section_boost_lifts_prepared_dampens_qa():
    boosts = BoostConfig(prepared_remarks=1.2, qa=0.8)
    pr, _ = apply_boosts(0.5, "prepared_remarks", None, boosts)
    qa, _ = apply_boosts(0.5, "qa", None, boosts)
    assert pr > 0.5
    assert qa < 0.5
    assert pr == pytest.approx(0.6, abs=1e-6)
    assert qa == pytest.approx(0.4, abs=1e-6)


def test_speaker_role_prefix_match():
    boosts = BoostConfig(speaker_role={"CEO": 1.3})
    # Exact match
    assert _speaker_boost(boosts, "CEO") == 1.3
    # Prefix-style: full title contains the key
    assert _speaker_boost(boosts, "Chief Executive Officer") == 1.0  # no startswith match
    # But startswith works
    assert _speaker_boost(boosts, "ceo, John Smith") == 1.3
    # Substring match (key inside the role)
    assert _speaker_boost(boosts, "Mr. CEO Smith") == 1.3
    # Unknown role → 1.0
    assert _speaker_boost(boosts, "Investor Relations") == 1.0


def test_section_and_speaker_compound():
    boosts = BoostConfig(
        prepared_remarks=1.1,
        speaker_role={"CEO": 1.2},
    )
    score, mult = apply_boosts(0.5, "prepared_remarks", "CEO", boosts)
    # Compounded: 1.1 * 1.2 = 1.32
    assert mult == pytest.approx(1.32, abs=1e-4)
    assert score == pytest.approx(0.5 * 1.32, abs=1e-6)


def test_boost_clamps_to_one():
    boosts = BoostConfig(
        prepared_remarks=1.5,
        speaker_role={"CEO": 1.5},
    )
    # Base 0.8 × 1.5 × 1.5 = 1.8 → clamped to 1.0
    score, mult = apply_boosts(0.8, "prepared_remarks", "CEO", boosts)
    assert score == 1.0
    assert mult == pytest.approx(2.25, abs=1e-4)


def test_section_boost_falls_back_to_full():
    boosts = BoostConfig(full=1.2)
    score, mult = apply_boosts(0.5, "full", None, boosts)
    assert mult == 1.2
    assert score == pytest.approx(0.6, abs=1e-6)


def test_section_boost_unknown_section_falls_back_to_full():
    boosts = BoostConfig(prepared_remarks=1.5, full=1.2)
    # An unrecognized section_type goes through the "full" multiplier
    assert _section_boost(boosts, "footnotes") == 1.2

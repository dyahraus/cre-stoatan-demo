"""Concept engine tests using a deterministic stub embedder.

We don't hit Voyage in tests — every concept gets a hand-rolled vector
and we compute cosine analytically. Lets us assert threshold gating,
saturation, and weighted contributions without external services.
"""

from __future__ import annotations

import math

import pytest

from warehouse_signal.analysis import concept_engine as ce
from warehouse_signal.analysis.concept_engine import (
    concept_score,
    detect,
    hits_summary_by_concept,
)
from warehouse_signal.analysis.embeddings import (
    NullEmbedder,
    cosine_similarity,
)
from warehouse_signal.models.schemas import (
    ConceptMode,
    KeywordCategory,
    SectionType,
    SignalConcept,
    TranscriptChunk,
)


class StubEmbedder:
    """Deterministic embedder. Concept text → predetermined vector via
    a name-to-vector dict; chunk text → vector hashed from words."""

    name = "stub"

    def __init__(self, table: dict[str, list[float]]):
        self.table = table

    def embed(self, text: str) -> list[float]:
        # Look up by exact text match first; fall back to a stable hash
        if text in self.table:
            return self.table[text]
        return self.table.get("__default__", [])

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


def _chunk(text: str = "irrelevant") -> TranscriptChunk:
    return TranscriptChunk(
        chunk_id="t",
        transcript_key="X_2024Q1",
        chunk_index=0,
        text=text,
        section_type=SectionType.PREPARED_REMARKS,
        token_estimate=10,
    )


def _concept(label: str, weight: float = 5.0, threshold: float = 0.65) -> SignalConcept:
    return SignalConcept(
        id=f"c-{label}",
        framework_id="fw",
        category=KeywordCategory.SUPPLY_CHAIN,
        label=label,
        description=label,  # used as cache key
        example_phrases=[],
        weight=weight,
        threshold=threshold,
        mode=ConceptMode.EMBEDDING,
    )


def setup_function():
    # Fresh cache between tests so concept text reuse is deterministic
    ce._concept_vector_cache.clear()


def test_cosine_helpers():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([], [1.0, 0.0]) == 0.0
    assert cosine_similarity([1.0], [1.0, 0.0]) == 0.0  # mismatched dim


def test_no_hits_when_below_threshold():
    concept = _concept("warehouse capacity", threshold=0.7)
    embedder = StubEmbedder(
        {
            "warehouse capacity": [1.0, 0.0],
        }
    )
    chunk = _chunk()
    chunk_vec = [0.6, 0.8]  # cosine = 0.6 — below 0.7 threshold
    hits = detect(chunk, [concept], chunk_vec, embedder=embedder)
    assert hits == []


def test_hit_fires_above_threshold_with_partial_weight():
    concept = _concept("warehouse capacity", weight=10.0, threshold=0.6)
    embedder = StubEmbedder(
        {"warehouse capacity": [1.0, 0.0]}
    )
    chunk = _chunk()
    chunk_vec = [0.8, 0.6]  # cosine = 0.8 — above 0.6 threshold
    hits = detect(chunk, [concept], chunk_vec, embedder=embedder)
    assert len(hits) == 1
    h = hits[0]
    assert h.label == "warehouse capacity"
    assert h.similarity == pytest.approx(0.8, abs=1e-3)
    # intensity = (0.8 - 0.6) / (1.0 - 0.6) = 0.5
    # contribution = 10.0 * 0.5 = 5.0
    assert h.weight_contribution == pytest.approx(5.0, abs=1e-3)


def test_perfect_match_gets_full_weight():
    concept = _concept("c", weight=8.0, threshold=0.5)
    embedder = StubEmbedder({"c": [1.0, 0.0]})
    hits = detect(_chunk(), [concept], [1.0, 0.0], embedder=embedder)
    assert len(hits) == 1
    assert hits[0].weight_contribution == pytest.approx(8.0)


def test_score_saturates_with_more_hits():
    embedder = StubEmbedder({"c1": [1.0, 0.0], "c2": [1.0, 0.0]})
    concepts = [
        _concept("c1", weight=10.0, threshold=0.5),
        _concept("c2", weight=10.0, threshold=0.5),
    ]
    hits = detect(_chunk(), concepts, [1.0, 0.0], embedder=embedder)
    one = concept_score(hits[:1])
    two = concept_score(hits)
    assert 0 < one < two < 1.0
    # Curve is 1 - exp(-Σw / 25); two perfect hits at w=10 each → 1 - e^(-20/25)
    assert two == pytest.approx(round(1 - math.exp(-20 / 25), 4), abs=1e-3)


def test_llm_mode_concept_skipped_silently():
    concept = SignalConcept(
        id="x",
        framework_id="fw",
        category=KeywordCategory.SUPPLY_CHAIN,
        label="llm-only",
        description="x",
        weight=5.0,
        threshold=0.5,
        mode=ConceptMode.LLM,
    )
    embedder = StubEmbedder({"x": [1.0, 0.0]})
    hits = detect(_chunk(), [concept], [1.0, 0.0], embedder=embedder)
    assert hits == []


def test_null_embedder_short_circuits():
    concept = _concept("c", threshold=0.5)
    hits = detect(_chunk(), [concept], [1.0, 0.0], embedder=NullEmbedder())
    assert hits == []


def test_empty_chunk_vector_skips_detection():
    concept = _concept("c", threshold=0.5)
    embedder = StubEmbedder({"c": [1.0, 0.0]})
    hits = detect(_chunk(), [concept], [], embedder=embedder)
    assert hits == []


def test_summary_groups_by_label():
    embedder = StubEmbedder({"c1": [1.0, 0.0], "c2": [1.0, 0.0]})
    concepts = [
        _concept("c1", threshold=0.5),
        _concept("c1", threshold=0.5),  # same label, different id
        _concept("c2", threshold=0.5),
    ]
    # Give them distinct ids
    concepts[1].id = "c-c1-2"
    hits = detect(_chunk(), concepts, [1.0, 0.0], embedder=embedder)
    summary = hits_summary_by_concept(hits)
    assert summary == {"c1": 2, "c2": 1}

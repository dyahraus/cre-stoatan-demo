"""Semantic concept detection via embeddings.

A concept is matched against a chunk by cosine similarity between the
chunk's embedding and the concept's embedding (description + example
phrases). When similarity ≥ threshold, a hit fires; the contribution
is weighted by how far above threshold the similarity sits.

Designed to be cheap: each chunk embeds once (cached on the chunks
table); concept vectors cache in-process. No re-embedding per scan.
"""

from __future__ import annotations

import math

from warehouse_signal.analysis.embeddings import (
    Embedder,
    NullEmbedder,
    cosine_similarity,
    get_embedder,
)
from warehouse_signal.models.schemas import (
    ConceptHit,
    ConceptMode,
    SignalConcept,
    SignalFramework,
    TranscriptChunk,
)

# Same saturation curve as keyword_engine — keeps concepts and keywords
# on the same scoring scale.
_SATURATION_K = 25.0

# In-process cache of concept_id -> embedding so we never re-embed a
# concept's example phrases in a single process lifetime.
_concept_vector_cache: dict[str, list[float]] = {}


def _concept_text(concept: SignalConcept) -> str:
    """Combine description + example phrases for embedding."""
    pieces = []
    if concept.description.strip():
        pieces.append(concept.description.strip())
    for p in concept.example_phrases:
        if p.strip():
            pieces.append(p.strip())
    if not pieces:
        pieces.append(concept.label)
    return " | ".join(pieces)


def concept_vector(concept: SignalConcept, embedder: Embedder) -> list[float]:
    """Cached embedding of a concept. Re-keys when the concept text changes."""
    cache_key = f"{concept.id}::{hash(_concept_text(concept))}"
    if cache_key in _concept_vector_cache:
        return _concept_vector_cache[cache_key]
    vec = embedder.embed(_concept_text(concept))
    _concept_vector_cache[cache_key] = vec
    return vec


def detect(
    chunk: TranscriptChunk,
    concepts: list[SignalConcept],
    chunk_vector: list[float],
    embedder: Embedder | None = None,
) -> list[ConceptHit]:
    """Run cosine similarity against every concept in `concepts`.

    `chunk_vector` is passed in so the caller can cache it across all
    frameworks/concepts touching the same chunk.
    """
    if not concepts or not chunk_vector:
        return []

    embedder = embedder or get_embedder()
    if isinstance(embedder, NullEmbedder):
        return []

    hits: list[ConceptHit] = []
    for concept in concepts:
        if concept.mode != ConceptMode.EMBEDDING:
            # LLM-mode concepts are reserved for a future phase; skip silently
            continue
        vec = concept_vector(concept, embedder)
        sim = cosine_similarity(chunk_vector, vec)
        if sim < concept.threshold:
            continue
        # Slope from threshold to 1.0 — barely-above hits contribute
        # little, near-perfect hits contribute full weight.
        denom = max(1e-6, 1.0 - concept.threshold)
        intensity = max(0.0, min(1.0, (sim - concept.threshold) / denom))
        contribution = concept.weight * intensity
        hits.append(
            ConceptHit(
                concept_id=concept.id,
                chunk_id=chunk.chunk_id,
                transcript_key=chunk.transcript_key,
                category=concept.category,
                label=concept.label,
                similarity=round(sim, 4),
                weight_contribution=round(contribution, 4),
                mode_used=ConceptMode.EMBEDDING,
            )
        )
    return hits


def concept_score(hits: list[ConceptHit]) -> float:
    """Saturation curve over concept hit weights → 0..1."""
    if not hits:
        return 0.0
    total = sum(h.weight_contribution for h in hits)
    return round(1.0 - math.exp(-total / _SATURATION_K), 4)


def hits_summary_by_concept(hits: list[ConceptHit]) -> dict[str, int]:
    """Per-concept hit counts for the framework breakdown chip."""
    out: dict[str, int] = {}
    for h in hits:
        out[h.label] = out.get(h.label, 0) + 1
    return out

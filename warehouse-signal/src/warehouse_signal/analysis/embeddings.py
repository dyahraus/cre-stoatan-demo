"""Pluggable embedding provider for semantic concept matching.

Default: Voyage AI (`voyage-3`, 1024-dim, $0.06/M tokens). Selectable
to OpenAI via `Config.EMBEDDING_PROVIDER`. When no key is configured,
the provider is the no-op `NullEmbedder` and concept-engine
short-circuits — the rest of the system continues working keyword-only.

The provider is intentionally tiny: text in, vector out, plus a cosine
helper. Embedding is the only external call; all caching happens
upstream (chunks have an `embedding_json` column; concept vectors
cache in-process).
"""

from __future__ import annotations

import math
from typing import Protocol

from warehouse_signal.config import Config


class Embedder(Protocol):
    name: str

    def embed(self, text: str) -> list[float]:
        ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        ...


class NullEmbedder:
    """Used when no API key is configured. Returns empty vectors so
    downstream cosine similarity is always 0 and no concept hits fire."""

    name = "null"

    def embed(self, text: str) -> list[float]:
        return []

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[] for _ in texts]


class VoyageEmbedder:
    """Voyage AI embeddings via the official SDK."""

    name = "voyage"

    def __init__(self) -> None:
        if not Config.VOYAGE_API_KEY:
            raise ValueError("VOYAGE_API_KEY is required for VoyageEmbedder.")
        # Lazy import — the dep is optional until someone enables the provider.
        import voyageai

        self._client = voyageai.Client(api_key=Config.VOYAGE_API_KEY)
        self._model = Config.VOYAGE_MODEL

    def embed(self, text: str) -> list[float]:
        if not text.strip():
            return []
        result = self._client.embed([text], model=self._model, input_type="document")
        return list(result.embeddings[0])

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        cleaned = [t for t in texts if t.strip()]
        if not cleaned:
            return [[] for _ in texts]
        result = self._client.embed(
            cleaned, model=self._model, input_type="document"
        )
        # Map back to the original index order, leaving empties for blanks
        out: list[list[float]] = []
        result_iter = iter(result.embeddings)
        for t in texts:
            if t.strip():
                out.append(list(next(result_iter)))
            else:
                out.append([])
        return out


class OpenAIEmbedder:
    """OpenAI text-embedding-3-small."""

    name = "openai"

    def __init__(self) -> None:
        if not Config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required for OpenAIEmbedder.")
        # Lazy import — only fail when actually used
        from openai import OpenAI

        self._client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self._model = Config.OPENAI_EMBEDDING_MODEL

    def embed(self, text: str) -> list[float]:
        if not text.strip():
            return []
        resp = self._client.embeddings.create(input=[text], model=self._model)
        return list(resp.data[0].embedding)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        cleaned_idx = [(i, t) for i, t in enumerate(texts) if t.strip()]
        if not cleaned_idx:
            return [[] for _ in texts]
        resp = self._client.embeddings.create(
            input=[t for _, t in cleaned_idx], model=self._model
        )
        out: list[list[float]] = [[] for _ in texts]
        for (orig_i, _), data in zip(cleaned_idx, resp.data):
            out[orig_i] = list(data.embedding)
        return out


def get_embedder() -> Embedder:
    """Return the configured embedder, or NullEmbedder when no key is set."""
    provider = (Config.EMBEDDING_PROVIDER or "").lower()
    if provider == "voyage" and Config.VOYAGE_API_KEY:
        return VoyageEmbedder()
    if provider == "openai" and Config.OPENAI_API_KEY:
        return OpenAIEmbedder()
    return NullEmbedder()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Standard cosine. Returns 0 for empty/mismatched vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)

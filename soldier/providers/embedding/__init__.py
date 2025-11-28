"""Embedding providers for text vectorization."""

from soldier.providers.embedding.base import EmbeddingProvider, EmbeddingResponse
from soldier.providers.embedding.mock import MockEmbeddingProvider

__all__ = [
    "EmbeddingProvider",
    "EmbeddingResponse",
    "MockEmbeddingProvider",
]

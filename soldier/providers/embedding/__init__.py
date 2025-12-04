"""Embedding providers for text vectorization."""

from soldier.providers.embedding.base import EmbeddingProvider, EmbeddingResponse
from soldier.providers.embedding.jina import JinaEmbeddingProvider
from soldier.providers.embedding.mock import MockEmbeddingProvider

__all__ = [
    "EmbeddingProvider",
    "EmbeddingResponse",
    "JinaEmbeddingProvider",
    "MockEmbeddingProvider",
]

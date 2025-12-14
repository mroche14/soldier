"""AI providers for LLM, embedding, and reranking capabilities.

This module consolidates all AI provider implementations:
- LLM: Text generation via Agno (OpenRouter, Anthropic, OpenAI, Groq)
- Embedding: Vector embeddings for semantic search (Jina, Voyage, Cohere, OpenAI)
- Rerank: Re-ordering search results by relevance (Jina, Cohere, CrossEncoder)
"""

from focal.infrastructure.providers.embedding.base import EmbeddingProvider
from focal.infrastructure.providers.embedding.jina import JinaEmbeddingProvider
from focal.infrastructure.providers.embedding.mock import MockEmbeddingProvider
from focal.infrastructure.providers.embedding.sentence_transformers import (
    SentenceTransformerEmbeddingProvider,
)
from focal.infrastructure.providers.llm.base import LLMProvider
from focal.infrastructure.providers.llm.executor import LLMExecutor
from focal.infrastructure.providers.llm.mock import MockLLMProvider
from focal.infrastructure.providers.rerank.base import RerankProvider
from focal.infrastructure.providers.rerank.jina import JinaRerankProvider
from focal.infrastructure.providers.rerank.mock import MockRerankProvider

__all__ = [
    # LLM
    "LLMProvider",
    "LLMExecutor",
    "MockLLMProvider",
    # Embedding
    "EmbeddingProvider",
    "JinaEmbeddingProvider",
    "MockEmbeddingProvider",
    "SentenceTransformerEmbeddingProvider",
    # Rerank
    "RerankProvider",
    "JinaRerankProvider",
    "MockRerankProvider",
]

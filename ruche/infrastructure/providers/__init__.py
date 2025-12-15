"""AI providers for LLM, embedding, and reranking capabilities.

This module consolidates all AI provider implementations:
- LLM: Text generation via Agno (OpenRouter, Anthropic, OpenAI, Groq)
- Embedding: Vector embeddings for semantic search (Jina, Voyage, Cohere, OpenAI)
- Rerank: Re-ordering search results by relevance (Jina, Cohere, CrossEncoder)
"""

from ruche.infrastructure.providers.embedding.base import EmbeddingProvider
from ruche.infrastructure.providers.embedding.jina import JinaEmbeddingProvider
from ruche.infrastructure.providers.embedding.mock import MockEmbeddingProvider

# Optional: SentenceTransformer requires sentence_transformers package
try:
    from ruche.infrastructure.providers.embedding.sentence_transformers import (
        SentenceTransformerEmbeddingProvider,
    )
except ImportError:
    SentenceTransformerEmbeddingProvider = None  # type: ignore
from ruche.infrastructure.providers.llm.executor import LLMExecutor
from ruche.infrastructure.providers.llm.mock import MockLLMProvider
from ruche.infrastructure.providers.rerank.base import RerankProvider
from ruche.infrastructure.providers.rerank.jina import JinaRerankProvider
from ruche.infrastructure.providers.rerank.mock import MockRerankProvider

__all__ = [
    # LLM
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

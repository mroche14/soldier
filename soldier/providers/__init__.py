"""External AI services: LLM, embedding, and reranking providers.

Abstract interfaces for AI capabilities with implementations for
Anthropic, OpenAI, Cohere, and other providers.
"""

from soldier.providers.embedding import EmbeddingProvider, MockEmbeddingProvider
from soldier.providers.llm import LLMProvider, MockLLMProvider
from soldier.providers.rerank import MockRerankProvider, RerankProvider

__all__ = [
    # LLM
    "LLMProvider",
    "MockLLMProvider",
    # Embedding
    "EmbeddingProvider",
    "MockEmbeddingProvider",
    # Rerank
    "RerankProvider",
    "MockRerankProvider",
]

"""External AI services: LLM, embedding, and reranking providers.

Abstract interfaces for AI capabilities with implementations for
Anthropic, OpenAI, Cohere, and other providers.

For LLM operations, use LLMExecutor which routes to the appropriate
backend (Agno models) based on model string.
"""

from focal.providers.embedding import EmbeddingProvider, MockEmbeddingProvider
from focal.providers.llm import LLMExecutor, MockLLMProvider
from focal.providers.rerank import MockRerankProvider, RerankProvider

__all__ = [
    # LLM (use LLMExecutor as primary interface)
    "LLMExecutor",
    "MockLLMProvider",
    # Embedding
    "EmbeddingProvider",
    "MockEmbeddingProvider",
    # Rerank
    "RerankProvider",
    "MockRerankProvider",
]

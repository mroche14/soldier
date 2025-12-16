"""Voyage AI embedding provider.

This is a placeholder for future implementation.
Voyage provides high-quality embeddings optimized for retrieval.

See docs/architecture/stub-files.md for implementation criteria.
"""

from ruche.infrastructure.providers.embedding.base import EmbeddingProvider


class VoyageEmbeddingProvider(EmbeddingProvider):
    """Embedding provider using Voyage AI API.

    Future implementation will support:
    - voyage-3 and voyage-3-lite models
    - voyage-code-3 for code embeddings
    - voyage-finance-2 for financial domain
    - voyage-law-2 for legal domain
    """

    def __init__(self) -> None:
        raise NotImplementedError(
            "VoyageEmbeddingProvider not yet implemented. "
            "Use OpenAIEmbeddingProvider, CohereEmbeddingProvider, or JinaEmbeddingProvider. "
            "Voyage implementation is planned for domain-specific embeddings."
        )

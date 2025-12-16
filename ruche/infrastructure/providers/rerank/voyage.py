"""Voyage AI rerank provider.

This is a placeholder for future implementation.
Voyage provides high-quality reranking optimized for retrieval.

See docs/architecture/stub-files.md for implementation criteria.
"""

from ruche.infrastructure.providers.rerank.base import RerankProvider


class VoyageRerankProvider(RerankProvider):
    """Rerank provider using Voyage AI API.

    Future implementation will support:
    - rerank-2 model
    - Domain-specific reranking
    - High accuracy retrieval optimization
    """

    def __init__(self) -> None:
        raise NotImplementedError(
            "VoyageRerankProvider not yet implemented. "
            "Use CohereRerankProvider or JinaRerankProvider. "
            "Voyage implementation is planned for domain-specific reranking."
        )

"""Cross-encoder rerank provider.

This is a placeholder for future implementation.
Cross-encoders provide high-quality reranking using local models.

See docs/architecture/stub-files.md for implementation criteria.
"""

from ruche.infrastructure.providers.rerank.base import RerankProvider


class CrossEncoderRerankProvider(RerankProvider):
    """Rerank provider using local cross-encoder models.

    Future implementation will support:
    - sentence-transformers cross-encoder models
    - Custom fine-tuned models
    - GPU acceleration
    - Batch processing
    """

    def __init__(self) -> None:
        raise NotImplementedError(
            "CrossEncoderRerankProvider not yet implemented. "
            "Use CohereRerankProvider or JinaRerankProvider. "
            "Cross-encoder implementation is planned for local/offline reranking."
        )

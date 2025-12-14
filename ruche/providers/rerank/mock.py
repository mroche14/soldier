"""Mock rerank provider for testing."""

from typing import Any

from ruche.providers.rerank.base import RerankProvider, RerankResponse, RerankResult


class MockRerankProvider(RerankProvider):
    """Mock rerank provider for testing.

    Uses simple text similarity for ranking without making API calls.
    """

    def __init__(
        self,
        default_model: str = "mock-rerank",
    ):
        """Initialize mock provider.

        Args:
            default_model: Model name to report
        """
        self._default_model = default_model
        self._call_history: list[dict[str, Any]] = []

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "mock"

    @property
    def call_history(self) -> list[dict[str, Any]]:
        """Return history of calls for testing assertions."""
        return self._call_history

    def clear_history(self) -> None:
        """Clear call history."""
        self._call_history.clear()

    def _compute_similarity(self, query: str, document: str) -> float:
        """Compute simple text similarity.

        Uses word overlap as a basic similarity measure.
        """
        query_words = set(query.lower().split())
        doc_words = set(document.lower().split())

        if not query_words or not doc_words:
            return 0.0

        intersection = query_words & doc_words
        union = query_words | doc_words

        # Jaccard similarity
        return len(intersection) / len(union) if union else 0.0

    async def rerank(
        self,
        query: str,
        documents: list[str],
        *,
        model: str | None = None,
        top_k: int | None = None,
        **kwargs: Any,
    ) -> RerankResponse:
        """Rerank documents using word overlap similarity."""
        # Record the call
        self._call_history.append({
            "query": query,
            "documents": documents,
            "model": model or self._default_model,
            "top_k": top_k,
            "kwargs": kwargs,
        })

        # Score each document
        scored = [
            (i, self._compute_similarity(query, doc), doc)
            for i, doc in enumerate(documents)
        ]

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        # Apply top_k limit
        if top_k is not None:
            scored = scored[:top_k]

        results = [
            RerankResult(index=idx, score=score, text=text)
            for idx, score, text in scored
        ]

        return RerankResponse(
            results=results,
            model=model or self._default_model,
            usage={
                "total_tokens": (len(query) + sum(len(d) for d in documents)) // 4,
            },
        )

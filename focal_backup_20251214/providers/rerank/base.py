"""RerankProvider abstract interface."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class RerankResult(BaseModel):
    """A single reranked result."""

    index: int = Field(..., description="Original index in input list")
    score: float = Field(..., description="Relevance score")
    text: str | None = Field(default=None, description="Document text")


class RerankResponse(BaseModel):
    """Response from a rerank provider."""

    results: list[RerankResult] = Field(..., description="Reranked results")
    model: str = Field(..., description="Model used")
    usage: dict[str, int] | None = Field(
        default=None, description="Token usage stats"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Provider-specific metadata"
    )


class RerankProvider(ABC):
    """Abstract interface for reranking.

    Provides unified access to various reranking providers
    (Cohere, Voyage, cross-encoders, etc.).
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""
        pass

    @abstractmethod
    async def rerank(
        self,
        query: str,
        documents: list[str],
        *,
        model: str | None = None,
        top_k: int | None = None,
        **kwargs: Any,
    ) -> RerankResponse:
        """Rerank documents by relevance to query.

        Args:
            query: Query to rank documents against
            documents: List of documents to rerank
            model: Model to use (provider default if not specified)
            top_k: Return only top K results (all if not specified)
            **kwargs: Provider-specific options

        Returns:
            RerankResponse with sorted results
        """
        pass

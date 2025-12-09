"""EmbeddingProvider abstract interface."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class EmbeddingResponse(BaseModel):
    """Response from an embedding provider."""

    embeddings: list[list[float]] = Field(..., description="Embedding vectors")
    model: str = Field(..., description="Model used")
    dimensions: int = Field(..., description="Vector dimensions")
    usage: dict[str, int] | None = Field(
        default=None, description="Token usage stats"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Provider-specific metadata"
    )


class EmbeddingProvider(ABC):
    """Abstract interface for text embeddings.

    Provides unified access to various embedding providers
    (OpenAI, Voyage, Cohere, etc.).
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""
        pass

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return the embedding dimensions."""
        pass

    @abstractmethod
    async def embed(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> EmbeddingResponse:
        """Generate embeddings for texts.

        Args:
            texts: List of texts to embed
            model: Model to use (provider default if not specified)
            **kwargs: Provider-specific options

        Returns:
            EmbeddingResponse with embedding vectors
        """
        pass

    async def embed_single(
        self,
        text: str,
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> list[float]:
        """Generate embedding for a single text.

        Convenience method that wraps embed() for single texts.

        Args:
            text: Text to embed
            model: Model to use (provider default if not specified)
            **kwargs: Provider-specific options

        Returns:
            Single embedding vector
        """
        response = await self.embed([text], model=model, **kwargs)
        return response.embeddings[0]

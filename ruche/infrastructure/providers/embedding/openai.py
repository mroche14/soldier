"""OpenAI embedding provider."""

import os
from typing import Any

from openai import AsyncOpenAI

from ruche.observability.logging import get_logger
from ruche.infrastructure.providers.embedding.base import EmbeddingProvider, EmbeddingResponse

logger = get_logger(__name__)


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Embedding provider using OpenAI API.

    Supports text-embedding-3-small, text-embedding-3-large, and text-embedding-ada-002.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "text-embedding-3-small",
        dimensions: int | None = None,
        timeout: float = 60.0,
    ):
        """Initialize OpenAI embedding provider.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Model identifier (text-embedding-3-small, text-embedding-3-large, text-embedding-ada-002)
            dimensions: Output embedding dimensions (only for text-embedding-3-* models)
            timeout: Request timeout in seconds
        """
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self._api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        self._model = model
        self._timeout = timeout
        self._client = AsyncOpenAI(api_key=self._api_key, timeout=timeout)

        # Set default dimensions based on model
        if dimensions is not None:
            self._dimensions = dimensions
        else:
            self._dimensions = self._get_default_dimensions(model)

    def _get_default_dimensions(self, model: str) -> int:
        """Get default dimensions for a model."""
        if model == "text-embedding-3-small":
            return 1536
        elif model == "text-embedding-3-large":
            return 3072
        elif model == "text-embedding-ada-002":
            return 1536
        else:
            return 1536  # Fallback

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "openai"

    @property
    def dimensions(self) -> int:
        """Return embedding dimensions."""
        return self._dimensions

    async def embed(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        dimensions: int | None = None,
        **kwargs: Any,
    ) -> EmbeddingResponse:
        """Generate embeddings using OpenAI API.

        Args:
            texts: List of texts to embed
            model: Model to use (defaults to configured model)
            dimensions: Output dimensions (only for text-embedding-3-* models)
            **kwargs: Additional options passed to API

        Returns:
            EmbeddingResponse with embedding vectors
        """
        use_model = model or self._model
        use_dimensions = dimensions or self._dimensions

        logger.debug(
            "openai_embed_request",
            model=use_model,
            dimensions=use_dimensions,
            num_texts=len(texts),
        )

        # Build API kwargs
        api_kwargs: dict[str, Any] = {
            "input": texts,
            "model": use_model,
        }

        # Only include dimensions for text-embedding-3-* models
        if use_model.startswith("text-embedding-3-"):
            api_kwargs["dimensions"] = use_dimensions

        # Add any extra kwargs
        api_kwargs.update(kwargs)

        try:
            response = await self._client.embeddings.create(**api_kwargs)
        except Exception as e:
            logger.error(
                "openai_embed_error",
                model=use_model,
                error=str(e),
            )
            raise RuntimeError(f"OpenAI API error: {e}") from e

        # Extract embeddings from response
        embeddings = [item.embedding for item in response.data]

        # Extract usage if available
        usage = None
        if response.usage:
            usage = {
                "total_tokens": response.usage.total_tokens,
                "prompt_tokens": response.usage.prompt_tokens,
            }

        logger.debug(
            "openai_embed_success",
            model=use_model,
            num_embeddings=len(embeddings),
            dimensions=len(embeddings[0]) if embeddings else 0,
        )

        return EmbeddingResponse(
            embeddings=embeddings,
            model=use_model,
            dimensions=use_dimensions,
            usage=usage,
            metadata={},
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.close()

    async def __aenter__(self) -> "OpenAIEmbeddingProvider":
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.close()

"""Cohere embedding provider."""

import os
from typing import Any, Literal

import httpx

from ruche.observability.logging import get_logger
from ruche.infrastructure.providers.embedding.base import EmbeddingProvider, EmbeddingResponse

logger = get_logger(__name__)

# Input types for Cohere embeddings
CohereInputType = Literal[
    "search_document",  # Embed documents for retrieval (indexing)
    "search_query",     # Embed queries for retrieval
    "classification",   # Text classification
    "clustering",       # Clustering or topic modeling
]


class CohereEmbeddingProvider(EmbeddingProvider):
    """Embedding provider using Cohere API.

    Supports embed-english-v3.0 and embed-multilingual-v3.0 models.
    """

    BASE_URL = "https://api.cohere.ai/v1/embed"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "embed-english-v3.0",
        default_input_type: CohereInputType = "search_document",
        timeout: float = 60.0,
    ):
        """Initialize Cohere embedding provider.

        Args:
            api_key: Cohere API key (defaults to COHERE_API_KEY env var)
            model: Model identifier (embed-english-v3.0, embed-multilingual-v3.0)
            default_input_type: Default input type for embeddings
            timeout: Request timeout in seconds
        """
        self._api_key = api_key or os.environ.get("COHERE_API_KEY")
        if not self._api_key:
            raise ValueError("COHERE_API_KEY environment variable not set")

        self._model = model
        self._default_input_type = default_input_type
        self._timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)
        self._dimensions = self._get_default_dimensions(model)

    def _get_default_dimensions(self, model: str) -> int:
        """Get default dimensions for a model."""
        if model in ("embed-english-v3.0", "embed-multilingual-v3.0"):
            return 1024
        else:
            return 1024  # Fallback

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "cohere"

    @property
    def dimensions(self) -> int:
        """Return embedding dimensions."""
        return self._dimensions

    async def embed(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        input_type: CohereInputType | None = None,
        **kwargs: Any,
    ) -> EmbeddingResponse:
        """Generate embeddings using Cohere API.

        Args:
            texts: List of texts to embed
            model: Model to use (defaults to configured model)
            input_type: Input type for embeddings (search_document, search_query, classification, clustering)
            **kwargs: Additional options passed to API

        Returns:
            EmbeddingResponse with embedding vectors
        """
        use_model = model or self._model
        use_input_type = input_type or self._default_input_type

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

        payload: dict[str, Any] = {
            "texts": texts,
            "model": use_model,
            "input_type": use_input_type,
            "embedding_types": ["float"],
        }

        # Add any extra kwargs
        payload.update(kwargs)

        logger.debug(
            "cohere_embed_request",
            model=use_model,
            input_type=use_input_type,
            num_texts=len(texts),
        )

        response = await self._client.post(
            self.BASE_URL,
            headers=headers,
            json=payload,
        )

        if response.status_code != 200:
            error_text = response.text
            logger.error(
                "cohere_embed_error",
                status_code=response.status_code,
                error=error_text,
            )
            raise RuntimeError(f"Cohere API error ({response.status_code}): {error_text}")

        data = response.json()

        # Extract embeddings from response
        embeddings = data["embeddings"]["float"]

        # Extract usage if available
        usage = None
        if "meta" in data and "billed_units" in data["meta"]:
            billed = data["meta"]["billed_units"]
            usage = {
                "total_tokens": billed.get("input_tokens", 0),
                "prompt_tokens": billed.get("input_tokens", 0),
            }

        logger.debug(
            "cohere_embed_success",
            model=use_model,
            num_embeddings=len(embeddings),
            dimensions=len(embeddings[0]) if embeddings else 0,
        )

        return EmbeddingResponse(
            embeddings=embeddings,
            model=use_model,
            dimensions=self._dimensions,
            usage=usage,
            metadata={
                "input_type": use_input_type,
            },
        )

    async def embed_query(
        self,
        text: str,
        **kwargs: Any,
    ) -> list[float]:
        """Embed a query for retrieval.

        Convenience method that uses the search_query input type.

        Args:
            text: Query text to embed
            **kwargs: Additional options

        Returns:
            Single embedding vector optimized for query retrieval
        """
        response = await self.embed([text], input_type="search_query", **kwargs)
        return response.embeddings[0]

    async def embed_documents(
        self,
        texts: list[str],
        **kwargs: Any,
    ) -> EmbeddingResponse:
        """Embed documents for retrieval indexing.

        Convenience method that uses the search_document input type.

        Args:
            texts: Document texts to embed
            **kwargs: Additional options

        Returns:
            EmbeddingResponse optimized for document retrieval
        """
        return await self.embed(texts, input_type="search_document", **kwargs)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "CohereEmbeddingProvider":
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.close()

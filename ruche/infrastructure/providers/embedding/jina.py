"""Jina AI embedding provider."""

import os
from typing import Any, Literal

import httpx

from ruche.observability.logging import get_logger
from ruche.infrastructure.providers.embedding.base import EmbeddingProvider, EmbeddingResponse

logger = get_logger(__name__)

# Task types for jina-embeddings-v3 LoRA adapters
JinaTaskType = Literal[
    "retrieval.query",    # Encode queries for retrieval
    "retrieval.passage",  # Encode documents for retrieval (indexing)
    "classification",     # Text classification
    "text-matching",      # Similarity matching
    "separation",         # Clustering or reranking
]


class JinaEmbeddingProvider(EmbeddingProvider):
    """Embedding provider using Jina AI API.

    Supports jina-embeddings-v3 with task-specific LoRA adapters
    and Matryoshka representation for flexible dimensions.
    """

    BASE_URL = "https://api.jina.ai/v1/embeddings"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "jina-embeddings-v3",
        dimensions: int = 1024,
        default_task: JinaTaskType = "retrieval.passage",
        timeout: float = 60.0,
    ):
        """Initialize Jina embedding provider.

        Args:
            api_key: Jina API key (defaults to JINA_API_KEY env var)
            model: Model identifier
            dimensions: Output embedding dimensions (32-1024 for v3)
            default_task: Default task type for LoRA adapter
            timeout: Request timeout in seconds
        """
        self._api_key = api_key or os.environ.get("JINA_API_KEY")
        if not self._api_key:
            raise ValueError("JINA_API_KEY environment variable not set")

        self._model = model
        self._dimensions = dimensions
        self._default_task = default_task
        self._timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "jina"

    @property
    def dimensions(self) -> int:
        """Return embedding dimensions."""
        return self._dimensions

    async def embed(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        task: JinaTaskType | None = None,
        dimensions: int | None = None,
        late_chunking: bool = False,
        **kwargs: Any,
    ) -> EmbeddingResponse:
        """Generate embeddings using Jina AI API.

        Args:
            texts: List of texts to embed
            model: Model to use (defaults to configured model)
            task: Task type for LoRA adapter optimization
            dimensions: Output dimensions (overrides configured default)
            late_chunking: Enable late chunking for contextual embeddings
            **kwargs: Additional options passed to API

        Returns:
            EmbeddingResponse with embedding vectors
        """
        use_model = model or self._model
        use_task = task or self._default_task
        use_dimensions = dimensions or self._dimensions

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

        payload: dict[str, Any] = {
            "input": texts,
            "model": use_model,
            "dimensions": use_dimensions,
            "task": use_task,
        }

        if late_chunking:
            payload["late_chunking"] = True

        # Add any extra kwargs
        payload.update(kwargs)

        logger.debug(
            "jina_embed_request",
            model=use_model,
            task=use_task,
            dimensions=use_dimensions,
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
                "jina_embed_error",
                status_code=response.status_code,
                error=error_text,
            )
            raise RuntimeError(f"Jina API error ({response.status_code}): {error_text}")

        data = response.json()

        # Extract embeddings from response
        embeddings = [item["embedding"] for item in data["data"]]

        # Extract usage if available
        usage = None
        if "usage" in data:
            usage = {
                "total_tokens": data["usage"].get("total_tokens", 0),
                "prompt_tokens": data["usage"].get("prompt_tokens", 0),
            }

        logger.debug(
            "jina_embed_success",
            model=use_model,
            num_embeddings=len(embeddings),
            dimensions=len(embeddings[0]) if embeddings else 0,
        )

        return EmbeddingResponse(
            embeddings=embeddings,
            model=use_model,
            dimensions=use_dimensions,
            usage=usage,
            metadata={
                "task": use_task,
                "late_chunking": late_chunking,
            },
        )

    async def embed_query(
        self,
        text: str,
        **kwargs: Any,
    ) -> list[float]:
        """Embed a query for retrieval.

        Convenience method that uses the retrieval.query task adapter.

        Args:
            text: Query text to embed
            **kwargs: Additional options

        Returns:
            Single embedding vector optimized for query retrieval
        """
        response = await self.embed([text], task="retrieval.query", **kwargs)
        return response.embeddings[0]

    async def embed_documents(
        self,
        texts: list[str],
        **kwargs: Any,
    ) -> EmbeddingResponse:
        """Embed documents for retrieval indexing.

        Convenience method that uses the retrieval.passage task adapter.

        Args:
            texts: Document texts to embed
            **kwargs: Additional options

        Returns:
            EmbeddingResponse optimized for document retrieval
        """
        return await self.embed(texts, task="retrieval.passage", **kwargs)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "JinaEmbeddingProvider":
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.close()

"""Jina AI rerank provider."""

import os
from typing import Any

import httpx

from focal.observability.logging import get_logger
from focal.providers.rerank.base import RerankProvider, RerankResponse, RerankResult

logger = get_logger(__name__)


class JinaRerankProvider(RerankProvider):
    """Rerank provider using Jina AI API.

    Supports jina-reranker-v2-base-multilingual and jina-reranker-v3
    for fast, accurate document reranking.
    """

    BASE_URL = "https://api.jina.ai/v1/rerank"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "jina-reranker-v2-base-multilingual",
        default_top_k: int = 10,
        timeout: float = 60.0,
    ):
        """Initialize Jina rerank provider.

        Args:
            api_key: Jina API key (defaults to JINA_API_KEY env var)
            model: Model identifier
            default_top_k: Default number of results to return
            timeout: Request timeout in seconds
        """
        self._api_key = api_key or os.environ.get("JINA_API_KEY")
        if not self._api_key:
            raise ValueError("JINA_API_KEY environment variable not set")

        self._model = model
        self._default_top_k = default_top_k
        self._timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "jina"

    async def rerank(
        self,
        query: str,
        documents: list[str],
        *,
        model: str | None = None,
        top_k: int | None = None,
        return_documents: bool = True,
        **kwargs: Any,
    ) -> RerankResponse:
        """Rerank documents by relevance to query.

        Args:
            query: Query to rank documents against
            documents: List of documents to rerank
            model: Model to use (defaults to configured model)
            top_k: Return only top K results
            return_documents: Include document text in response
            **kwargs: Additional options passed to API

        Returns:
            RerankResponse with sorted results
        """
        if not documents:
            return RerankResponse(
                results=[],
                model=model or self._model,
                usage={"total_tokens": 0},
            )

        use_model = model or self._model
        use_top_k = top_k if top_k is not None else self._default_top_k

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

        payload: dict[str, Any] = {
            "model": use_model,
            "query": query,
            "documents": documents,
            "top_n": use_top_k,
            "return_documents": return_documents,
        }

        # Add any extra kwargs
        payload.update(kwargs)

        logger.debug(
            "jina_rerank_request",
            model=use_model,
            query_len=len(query),
            num_documents=len(documents),
            top_k=use_top_k,
        )

        response = await self._client.post(
            self.BASE_URL,
            headers=headers,
            json=payload,
        )

        if response.status_code != 200:
            error_text = response.text
            logger.error(
                "jina_rerank_error",
                status_code=response.status_code,
                error=error_text,
            )
            raise RuntimeError(f"Jina API error ({response.status_code}): {error_text}")

        data = response.json()

        # Parse results
        results = []
        for item in data.get("results", []):
            text = None
            if return_documents and "document" in item:
                text = item["document"].get("text")

            results.append(
                RerankResult(
                    index=item["index"],
                    score=item["relevance_score"],
                    text=text,
                )
            )

        # Extract usage if available
        usage = None
        if "usage" in data:
            usage = {
                "total_tokens": data["usage"].get("total_tokens", 0),
                "prompt_tokens": data["usage"].get("prompt_tokens", 0),
            }

        logger.debug(
            "jina_rerank_success",
            model=use_model,
            num_results=len(results),
            top_score=results[0].score if results else 0,
        )

        return RerankResponse(
            results=results,
            model=use_model,
            usage=usage,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "JinaRerankProvider":
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.close()

"""Cohere rerank provider."""

import os
from typing import Any

import httpx

from ruche.observability.logging import get_logger
from ruche.infrastructure.providers.rerank.base import RerankProvider, RerankResponse, RerankResult

logger = get_logger(__name__)


class CohereRerankProvider(RerankProvider):
    """Rerank provider using Cohere API.

    Supports rerank-english-v3.0 and rerank-multilingual-v3.0
    for fast, accurate document reranking.
    """

    BASE_URL = "https://api.cohere.ai/v1/rerank"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "rerank-english-v3.0",
        default_top_k: int = 10,
        timeout: float = 60.0,
    ):
        """Initialize Cohere rerank provider.

        Args:
            api_key: Cohere API key (defaults to COHERE_API_KEY env var)
            model: Model identifier (rerank-english-v3.0 or rerank-multilingual-v3.0)
            default_top_k: Default number of results to return
            timeout: Request timeout in seconds
        """
        self._api_key = api_key or os.environ.get("COHERE_API_KEY")
        if not self._api_key:
            raise ValueError("COHERE_API_KEY environment variable not set")

        self._model = model
        self._default_top_k = default_top_k
        self._timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "cohere"

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
            "cohere_rerank_request",
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
                "cohere_rerank_error",
                status_code=response.status_code,
                error=error_text,
            )
            raise RuntimeError(f"Cohere API error ({response.status_code}): {error_text}")

        data = response.json()

        # Parse results
        results = []
        for item in data.get("results", []):
            text = None
            if return_documents and "document" in item:
                # Cohere returns document as a dict with a "text" field
                doc = item["document"]
                text = doc.get("text") if isinstance(doc, dict) else doc

            results.append(
                RerankResult(
                    index=item["index"],
                    score=item["relevance_score"],
                    text=text,
                )
            )

        # Extract usage if available
        usage = None
        if "meta" in data and "billed_units" in data["meta"]:
            # Cohere uses billed_units instead of tokens
            billed = data["meta"]["billed_units"]
            usage = {
                "total_tokens": billed.get("search_units", 0),
            }

        logger.debug(
            "cohere_rerank_success",
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

    async def __aenter__(self) -> "CohereRerankProvider":
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.close()

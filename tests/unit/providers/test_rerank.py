"""Tests for rerank providers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ruche.infrastructure.providers.rerank import JinaRerankProvider, MockRerankProvider, RerankResponse


class TestMockRerankProvider:
    """Tests for MockRerankProvider."""

    @pytest.fixture
    def provider(self) -> MockRerankProvider:
        """Create a mock provider."""
        return MockRerankProvider()

    @pytest.mark.asyncio
    async def test_rerank_documents(self, provider):
        """Should rerank documents by relevance."""
        query = "python programming"
        documents = [
            "Java is a programming language",
            "Python is great for programming",
            "Cooking recipes are fun",
        ]

        response = await provider.rerank(query, documents)

        assert isinstance(response, RerankResponse)
        assert len(response.results) == 3
        # Python doc should rank highest
        assert response.results[0].text == "Python is great for programming"

    @pytest.mark.asyncio
    async def test_rerank_top_k(self, provider):
        """Should limit results to top_k."""
        query = "test"
        documents = ["test one", "test two", "test three", "other"]

        response = await provider.rerank(query, documents, top_k=2)

        assert len(response.results) == 2

    @pytest.mark.asyncio
    async def test_results_include_original_index(self, provider):
        """Should preserve original document indices."""
        query = "test"
        documents = ["other", "test match", "another"]

        response = await provider.rerank(query, documents)

        # Find the best match
        best = response.results[0]
        assert best.index == 1  # "test match" was at index 1
        assert best.text == "test match"

    @pytest.mark.asyncio
    async def test_scores_are_decreasing(self, provider):
        """Should return results sorted by score descending."""
        query = "search query"
        documents = ["doc1", "doc2", "doc3"]

        response = await provider.rerank(query, documents)

        scores = [r.score for r in response.results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_provider_name(self, provider):
        """Should return provider name."""
        assert provider.provider_name == "mock"

    @pytest.mark.asyncio
    async def test_tracks_call_history(self, provider):
        """Should track call history."""
        await provider.rerank("query", ["doc1", "doc2"])

        assert len(provider.call_history) == 1
        assert provider.call_history[0]["query"] == "query"

    @pytest.mark.asyncio
    async def test_clear_history(self, provider):
        """Should clear call history."""
        await provider.rerank("query", ["doc"])
        assert len(provider.call_history) == 1

        provider.clear_history()
        assert len(provider.call_history) == 0

    @pytest.mark.asyncio
    async def test_usage_tracking(self, provider):
        """Should track token usage."""
        response = await provider.rerank("query", ["doc1", "doc2"])

        assert response.usage is not None
        assert "total_tokens" in response.usage

    @pytest.mark.asyncio
    async def test_empty_documents(self, provider):
        """Should handle empty document list."""
        response = await provider.rerank("query", [])

        assert len(response.results) == 0

    @pytest.mark.asyncio
    async def test_similarity_scoring(self, provider):
        """Should score based on word overlap."""
        query = "hello world"
        documents = [
            "hello world",  # Perfect match
            "hello",  # Partial match
            "goodbye",  # No match
        ]

        response = await provider.rerank(query, documents)

        assert response.results[0].text == "hello world"
        assert response.results[0].score > response.results[1].score
        assert response.results[1].score > response.results[2].score


class TestJinaRerankProvider:
    """Tests for JinaRerankProvider."""

    @pytest.fixture
    def mock_response(self):
        """Create a mock API response."""
        return {
            "results": [
                {"index": 1, "relevance_score": 0.95, "document": {"text": "Python programming"}},
                {"index": 0, "relevance_score": 0.80, "document": {"text": "Java programming"}},
                {"index": 2, "relevance_score": 0.30, "document": {"text": "Cooking recipes"}},
            ],
            "usage": {"total_tokens": 50, "prompt_tokens": 50},
        }

    @pytest.fixture
    def provider(self):
        """Create a Jina provider with mocked API key."""
        with patch.dict("os.environ", {"JINA_API_KEY": "test-key"}):
            return JinaRerankProvider()

    @pytest.mark.asyncio
    async def test_provider_name(self, provider):
        """Should return provider name."""
        assert provider.provider_name == "jina"

    @pytest.mark.asyncio
    async def test_rerank_documents(self, provider, mock_response):
        """Should rerank documents via API."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response

        provider._client.post = AsyncMock(return_value=mock_http_response)

        response = await provider.rerank(
            "python programming",
            ["Java programming", "Python programming", "Cooking recipes"],
        )

        assert isinstance(response, RerankResponse)
        assert len(response.results) == 3
        assert response.results[0].index == 1
        assert response.results[0].score == 0.95
        assert response.results[0].text == "Python programming"

    @pytest.mark.asyncio
    async def test_rerank_top_k(self, provider, mock_response):
        """Should pass top_n parameter to API."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response

        provider._client.post = AsyncMock(return_value=mock_http_response)

        await provider.rerank("query", ["doc1", "doc2", "doc3"], top_k=2)

        call_args = provider._client.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["top_n"] == 2

    @pytest.mark.asyncio
    async def test_empty_documents(self, provider):
        """Should handle empty document list."""
        response = await provider.rerank("query", [])

        assert len(response.results) == 0
        assert response.usage["total_tokens"] == 0

    @pytest.mark.asyncio
    async def test_api_error_raises_exception(self, provider):
        """Should raise exception on API error."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 401
        mock_http_response.text = "Unauthorized"

        provider._client.post = AsyncMock(return_value=mock_http_response)

        with pytest.raises(RuntimeError, match="Jina API error"):
            await provider.rerank("query", ["doc"])

    @pytest.mark.asyncio
    async def test_usage_tracking(self, provider, mock_response):
        """Should include usage stats in response."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response

        provider._client.post = AsyncMock(return_value=mock_http_response)

        response = await provider.rerank("query", ["doc1", "doc2"])

        assert response.usage is not None
        assert response.usage["total_tokens"] == 50

    @pytest.mark.asyncio
    async def test_return_documents_flag(self, provider, mock_response):
        """Should pass return_documents to API."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response

        provider._client.post = AsyncMock(return_value=mock_http_response)

        await provider.rerank("query", ["doc"], return_documents=False)

        call_args = provider._client.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["return_documents"] is False

    @pytest.mark.asyncio
    async def test_model_override(self, provider, mock_response):
        """Should allow model override."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response

        provider._client.post = AsyncMock(return_value=mock_http_response)

        response = await provider.rerank(
            "query", ["doc"], model="jina-reranker-v3"
        )

        call_args = provider._client.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["model"] == "jina-reranker-v3"
        assert response.model == "jina-reranker-v3"

    def test_missing_api_key_raises_error(self):
        """Should raise error if API key not provided."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="JINA_API_KEY"):
                JinaRerankProvider()

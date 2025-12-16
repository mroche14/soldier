"""Tests for Cohere rerank provider."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ruche.infrastructure.providers.rerank import CohereRerankProvider, RerankResponse


class TestCohereRerankProvider:
    """Tests for CohereRerankProvider."""

    @pytest.fixture
    def mock_response(self):
        """Create a mock API response."""
        return {
            "results": [
                {
                    "index": 1,
                    "relevance_score": 0.95,
                    "document": {"text": "Python programming"},
                },
                {
                    "index": 0,
                    "relevance_score": 0.80,
                    "document": {"text": "Java programming"},
                },
                {
                    "index": 2,
                    "relevance_score": 0.30,
                    "document": {"text": "Cooking recipes"},
                },
            ],
            "meta": {
                "billed_units": {
                    "search_units": 50,
                }
            },
        }

    @pytest.fixture
    def provider(self):
        """Create a Cohere provider with mocked API key."""
        with patch.dict("os.environ", {"COHERE_API_KEY": "test-key"}):
            return CohereRerankProvider()

    @pytest.mark.asyncio
    async def test_provider_name(self, provider):
        """Should return provider name."""
        assert provider.provider_name == "cohere"

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

        with pytest.raises(RuntimeError, match="Cohere API error"):
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
            "query", ["doc"], model="rerank-multilingual-v3.0"
        )

        call_args = provider._client.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["model"] == "rerank-multilingual-v3.0"
        assert response.model == "rerank-multilingual-v3.0"

    def test_missing_api_key_raises_error(self):
        """Should raise error if API key not provided."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="COHERE_API_KEY"):
                CohereRerankProvider()

    @pytest.mark.asyncio
    async def test_default_top_k(self, provider, mock_response):
        """Should use default top_k when not specified."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response

        provider._client.post = AsyncMock(return_value=mock_http_response)

        await provider.rerank("query", ["doc1", "doc2"])

        call_args = provider._client.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["top_n"] == 10

    @pytest.mark.asyncio
    async def test_custom_default_top_k(self, mock_response):
        """Should accept custom default top_k via constructor."""
        with patch.dict("os.environ", {"COHERE_API_KEY": "test-key"}):
            provider = CohereRerankProvider(default_top_k=5)

            mock_http_response = MagicMock()
            mock_http_response.status_code = 200
            mock_http_response.json.return_value = mock_response

            provider._client.post = AsyncMock(return_value=mock_http_response)

            await provider.rerank("query", ["doc1", "doc2"])

            call_args = provider._client.post.call_args
            payload = call_args.kwargs["json"]
            assert payload["top_n"] == 5

    @pytest.mark.asyncio
    async def test_custom_timeout(self):
        """Should accept custom timeout via constructor."""
        with patch.dict("os.environ", {"COHERE_API_KEY": "test-key"}):
            provider = CohereRerankProvider(timeout=120.0)
            assert provider._timeout == 120.0

    @pytest.mark.asyncio
    async def test_close_client(self, provider):
        """Should close HTTP client."""
        provider._client.aclose = AsyncMock()
        await provider.close()
        provider._client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_context_manager(self, mock_response):
        """Should work as async context manager."""
        with patch.dict("os.environ", {"COHERE_API_KEY": "test-key"}):
            async with CohereRerankProvider() as provider:
                mock_http_response = MagicMock()
                mock_http_response.status_code = 200
                mock_http_response.json.return_value = mock_response

                provider._client.post = AsyncMock(return_value=mock_http_response)

                response = await provider.rerank("query", ["doc1", "doc2"])
                assert len(response.results) == 3

    @pytest.mark.asyncio
    async def test_extra_kwargs_passed_to_api(self, provider, mock_response):
        """Should pass extra kwargs to API."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response

        provider._client.post = AsyncMock(return_value=mock_http_response)

        await provider.rerank("query", ["doc"], max_chunks_per_doc=10)

        call_args = provider._client.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["max_chunks_per_doc"] == 10

    @pytest.mark.asyncio
    async def test_authorization_header(self, provider, mock_response):
        """Should include authorization header with Bearer token."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response

        provider._client.post = AsyncMock(return_value=mock_http_response)

        await provider.rerank("query", ["doc"])

        call_args = provider._client.post.call_args
        headers = call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer test-key"

    @pytest.mark.asyncio
    async def test_response_without_usage(self, provider):
        """Should handle response without usage information."""
        mock_no_usage_response = {
            "results": [
                {"index": 0, "relevance_score": 0.9, "document": {"text": "Test"}},
            ],
        }
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_no_usage_response

        provider._client.post = AsyncMock(return_value=mock_http_response)

        response = await provider.rerank("query", ["Test"])

        assert response.usage is None
        assert len(response.results) == 1

    @pytest.mark.asyncio
    async def test_document_as_string_instead_of_dict(self, provider):
        """Should handle document returned as string instead of dict."""
        mock_string_doc_response = {
            "results": [
                {"index": 0, "relevance_score": 0.9, "document": "Plain text"},
            ],
            "meta": {"billed_units": {"search_units": 10}},
        }
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_string_doc_response

        provider._client.post = AsyncMock(return_value=mock_http_response)

        response = await provider.rerank("query", ["Test"])

        assert response.results[0].text == "Plain text"

    @pytest.mark.asyncio
    async def test_return_documents_false_no_text(self, provider):
        """Should handle return_documents=False with no document text."""
        mock_no_docs_response = {
            "results": [
                {"index": 0, "relevance_score": 0.9},
            ],
            "meta": {"billed_units": {"search_units": 10}},
        }
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_no_docs_response

        provider._client.post = AsyncMock(return_value=mock_http_response)

        response = await provider.rerank("query", ["Test"], return_documents=False)

        assert response.results[0].text is None
        assert response.results[0].score == 0.9

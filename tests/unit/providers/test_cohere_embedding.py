"""Tests for Cohere embedding provider."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ruche.infrastructure.providers.embedding import CohereEmbeddingProvider, EmbeddingResponse


class TestCohereEmbeddingProvider:
    """Tests for CohereEmbeddingProvider."""

    @pytest.fixture
    def mock_response(self):
        """Create a mock API response."""
        return {
            "embeddings": {
                "float": [
                    [0.1] * 1024,
                    [0.2] * 1024,
                ]
            },
            "meta": {
                "billed_units": {
                    "input_tokens": 10,
                }
            },
        }

    @pytest.fixture
    def provider(self):
        """Create a Cohere provider with mocked API key."""
        with patch.dict("os.environ", {"COHERE_API_KEY": "test-key"}):
            return CohereEmbeddingProvider(model="embed-english-v3.0")

    @pytest.mark.asyncio
    async def test_provider_name(self, provider):
        """Should return provider name."""
        assert provider.provider_name == "cohere"

    @pytest.mark.asyncio
    async def test_dimensions_property(self, provider):
        """Should return configured dimensions."""
        assert provider.dimensions == 1024

    @pytest.mark.asyncio
    async def test_embed_texts(self, provider, mock_response):
        """Should embed multiple texts via API."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response

        provider._client.post = AsyncMock(return_value=mock_http_response)

        response = await provider.embed(["Hello", "World"])

        assert isinstance(response, EmbeddingResponse)
        assert len(response.embeddings) == 2
        assert response.model == "embed-english-v3.0"
        assert response.dimensions == 1024

    @pytest.mark.asyncio
    async def test_embed_with_custom_model(self, provider, mock_response):
        """Should use custom model when specified."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response

        provider._client.post = AsyncMock(return_value=mock_http_response)

        await provider.embed(["Test"], model="embed-multilingual-v3.0")

        call_args = provider._client.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["model"] == "embed-multilingual-v3.0"

    @pytest.mark.asyncio
    async def test_embed_with_input_type(self, provider, mock_response):
        """Should pass input_type parameter to API."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response

        provider._client.post = AsyncMock(return_value=mock_http_response)

        await provider.embed(["Test"], input_type="search_query")

        call_args = provider._client.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["input_type"] == "search_query"

    @pytest.mark.asyncio
    async def test_embed_query_uses_search_query_input_type(self, provider, mock_response):
        """Should use search_query input type for embed_query."""
        mock_response["embeddings"]["float"] = [[0.1] * 1024]
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response

        provider._client.post = AsyncMock(return_value=mock_http_response)

        embedding = await provider.embed_query("Search query")

        call_args = provider._client.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["input_type"] == "search_query"
        assert isinstance(embedding, list)
        assert len(embedding) == 1024

    @pytest.mark.asyncio
    async def test_embed_documents_uses_search_document_input_type(self, provider, mock_response):
        """Should use search_document input type for embed_documents."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response

        provider._client.post = AsyncMock(return_value=mock_http_response)

        response = await provider.embed_documents(["Doc 1", "Doc 2"])

        call_args = provider._client.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["input_type"] == "search_document"
        assert len(response.embeddings) == 2

    @pytest.mark.asyncio
    async def test_api_error_raises_exception(self, provider):
        """Should raise exception on API error."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 401
        mock_http_response.text = "Unauthorized"

        provider._client.post = AsyncMock(return_value=mock_http_response)

        with pytest.raises(RuntimeError, match="Cohere API error"):
            await provider.embed(["Test"])

    @pytest.mark.asyncio
    async def test_usage_tracking(self, provider, mock_response):
        """Should include usage stats in response."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response

        provider._client.post = AsyncMock(return_value=mock_http_response)

        response = await provider.embed(["Test", "Test2"])

        assert response.usage is not None
        assert response.usage["total_tokens"] == 10
        assert response.usage["prompt_tokens"] == 10

    @pytest.mark.asyncio
    async def test_metadata_includes_input_type(self, provider, mock_response):
        """Should include input_type in metadata."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response

        provider._client.post = AsyncMock(return_value=mock_http_response)

        response = await provider.embed(["Test"], input_type="classification")

        assert response.metadata["input_type"] == "classification"

    def test_missing_api_key_raises_error(self):
        """Should raise error if API key not provided."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="COHERE_API_KEY"):
                CohereEmbeddingProvider()

    @pytest.mark.asyncio
    async def test_default_input_type(self, provider, mock_response):
        """Should use default input_type when not specified."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response

        provider._client.post = AsyncMock(return_value=mock_http_response)

        await provider.embed(["Test"])

        call_args = provider._client.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["input_type"] == "search_document"

    @pytest.mark.asyncio
    async def test_custom_default_input_type(self, mock_response):
        """Should accept custom default input_type via constructor."""
        with patch.dict("os.environ", {"COHERE_API_KEY": "test-key"}):
            provider = CohereEmbeddingProvider(default_input_type="clustering")

            mock_http_response = MagicMock()
            mock_http_response.status_code = 200
            mock_http_response.json.return_value = mock_response

            provider._client.post = AsyncMock(return_value=mock_http_response)

            await provider.embed(["Test"])

            call_args = provider._client.post.call_args
            payload = call_args.kwargs["json"]
            assert payload["input_type"] == "clustering"

    @pytest.mark.asyncio
    async def test_custom_timeout(self):
        """Should accept custom timeout via constructor."""
        with patch.dict("os.environ", {"COHERE_API_KEY": "test-key"}):
            provider = CohereEmbeddingProvider(timeout=120.0)
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
            async with CohereEmbeddingProvider() as provider:
                mock_http_response = MagicMock()
                mock_http_response.status_code = 200
                mock_http_response.json.return_value = mock_response

                provider._client.post = AsyncMock(return_value=mock_http_response)

                response = await provider.embed(["Test"])
                assert len(response.embeddings) == 2

    @pytest.mark.asyncio
    async def test_extra_kwargs_passed_to_api(self, provider, mock_response):
        """Should pass extra kwargs to API."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response

        provider._client.post = AsyncMock(return_value=mock_http_response)

        await provider.embed(["Test"], truncate="END")

        call_args = provider._client.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["truncate"] == "END"

    @pytest.mark.asyncio
    async def test_authorization_header(self, provider, mock_response):
        """Should include authorization header with Bearer token."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response

        provider._client.post = AsyncMock(return_value=mock_http_response)

        await provider.embed(["Test"])

        call_args = provider._client.post.call_args
        headers = call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer test-key"

    @pytest.mark.asyncio
    async def test_response_without_usage(self, provider):
        """Should handle response without usage information."""
        mock_no_usage_response = {
            "embeddings": {
                "float": [[0.1] * 1024],
            },
        }
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_no_usage_response

        provider._client.post = AsyncMock(return_value=mock_http_response)

        response = await provider.embed(["Test"])

        assert response.usage is None
        assert len(response.embeddings) == 1

    @pytest.mark.asyncio
    async def test_default_dimensions_for_multilingual_model(self):
        """Should use 1024 dimensions for embed-multilingual-v3.0."""
        with patch.dict("os.environ", {"COHERE_API_KEY": "test-key"}):
            provider = CohereEmbeddingProvider(model="embed-multilingual-v3.0")
            assert provider.dimensions == 1024

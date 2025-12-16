"""Tests for OpenAI embedding provider."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ruche.infrastructure.providers.embedding import EmbeddingResponse, OpenAIEmbeddingProvider


class TestOpenAIEmbeddingProvider:
    """Tests for OpenAIEmbeddingProvider."""

    @pytest.fixture
    def mock_response(self):
        """Create a mock API response."""
        mock_obj = MagicMock()
        mock_obj.data = [
            MagicMock(embedding=[0.1] * 1536),
            MagicMock(embedding=[0.2] * 1536),
        ]
        mock_obj.usage = MagicMock(total_tokens=10, prompt_tokens=10)
        return mock_obj

    @pytest.fixture
    def provider(self):
        """Create an OpenAI provider with mocked API key."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            return OpenAIEmbeddingProvider(model="text-embedding-3-small")

    @pytest.mark.asyncio
    async def test_provider_name(self, provider):
        """Should return provider name."""
        assert provider.provider_name == "openai"

    @pytest.mark.asyncio
    async def test_dimensions_property(self, provider):
        """Should return configured dimensions."""
        assert provider.dimensions == 1536

    @pytest.mark.asyncio
    async def test_embed_texts(self, provider, mock_response):
        """Should embed multiple texts via API."""
        provider._client.embeddings.create = AsyncMock(return_value=mock_response)

        response = await provider.embed(["Hello", "World"])

        assert isinstance(response, EmbeddingResponse)
        assert len(response.embeddings) == 2
        assert response.model == "text-embedding-3-small"
        assert response.dimensions == 1536

    @pytest.mark.asyncio
    async def test_embed_with_custom_model(self, provider, mock_response):
        """Should use custom model when specified."""
        provider._client.embeddings.create = AsyncMock(return_value=mock_response)

        await provider.embed(["Test"], model="text-embedding-3-large")

        call_args = provider._client.embeddings.create.call_args
        assert call_args.kwargs["model"] == "text-embedding-3-large"

    @pytest.mark.asyncio
    async def test_embed_with_custom_dimensions(self, provider, mock_response):
        """Should use custom dimensions for text-embedding-3-* models."""
        provider._client.embeddings.create = AsyncMock(return_value=mock_response)

        await provider.embed(["Test"], dimensions=512)

        call_args = provider._client.embeddings.create.call_args
        assert call_args.kwargs["dimensions"] == 512

    @pytest.mark.asyncio
    async def test_embed_single(self, provider, mock_response):
        """Should embed single text."""
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        provider._client.embeddings.create = AsyncMock(return_value=mock_response)

        embedding = await provider.embed_single("Test")

        assert isinstance(embedding, list)
        assert len(embedding) == 1536

    @pytest.mark.asyncio
    async def test_api_error_raises_exception(self, provider):
        """Should raise exception on API error."""
        provider._client.embeddings.create = AsyncMock(
            side_effect=Exception("API Error")
        )

        with pytest.raises(RuntimeError, match="OpenAI API error"):
            await provider.embed(["Test"])

    @pytest.mark.asyncio
    async def test_usage_tracking(self, provider, mock_response):
        """Should include usage stats in response."""
        provider._client.embeddings.create = AsyncMock(return_value=mock_response)

        response = await provider.embed(["Test", "Test2"])

        assert response.usage is not None
        assert response.usage["total_tokens"] == 10

    @pytest.mark.asyncio
    async def test_default_dimensions_text_embedding_3_small(self):
        """Should use 1536 dimensions for text-embedding-3-small."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")
            assert provider.dimensions == 1536

    @pytest.mark.asyncio
    async def test_default_dimensions_text_embedding_3_large(self):
        """Should use 3072 dimensions for text-embedding-3-large."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            provider = OpenAIEmbeddingProvider(model="text-embedding-3-large")
            assert provider.dimensions == 3072

    @pytest.mark.asyncio
    async def test_default_dimensions_ada_002(self):
        """Should use 1536 dimensions for text-embedding-ada-002."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            provider = OpenAIEmbeddingProvider(model="text-embedding-ada-002")
            assert provider.dimensions == 1536

    def test_missing_api_key_raises_error(self):
        """Should raise error if API key not provided."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                OpenAIEmbeddingProvider()

    @pytest.mark.asyncio
    async def test_dimensions_not_included_for_ada_002(self, provider, mock_response):
        """Should not include dimensions parameter for ada-002 model."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            ada_provider = OpenAIEmbeddingProvider(model="text-embedding-ada-002")
            ada_provider._client.embeddings.create = AsyncMock(return_value=mock_response)

            await ada_provider.embed(["Test"])

            call_args = ada_provider._client.embeddings.create.call_args
            assert "dimensions" not in call_args.kwargs

    @pytest.mark.asyncio
    async def test_dimensions_included_for_text_embedding_3(self, provider, mock_response):
        """Should include dimensions parameter for text-embedding-3-* models."""
        provider._client.embeddings.create = AsyncMock(return_value=mock_response)

        await provider.embed(["Test"])

        call_args = provider._client.embeddings.create.call_args
        assert call_args.kwargs["dimensions"] == 1536

    @pytest.mark.asyncio
    async def test_custom_api_key_via_constructor(self, mock_response):
        """Should accept custom API key via constructor."""
        provider = OpenAIEmbeddingProvider(api_key="custom-key")
        assert provider._api_key == "custom-key"

    @pytest.mark.asyncio
    async def test_custom_timeout_via_constructor(self):
        """Should accept custom timeout via constructor."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            provider = OpenAIEmbeddingProvider(timeout=120.0)
            assert provider._timeout == 120.0

    @pytest.mark.asyncio
    async def test_close_client(self, provider):
        """Should close HTTP client."""
        provider._client.close = AsyncMock()
        await provider.close()
        provider._client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_context_manager(self, mock_response):
        """Should work as async context manager."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            async with OpenAIEmbeddingProvider() as provider:
                provider._client.embeddings.create = AsyncMock(return_value=mock_response)
                response = await provider.embed(["Test"])
                assert len(response.embeddings) == 2

    @pytest.mark.asyncio
    async def test_extra_kwargs_passed_to_api(self, provider, mock_response):
        """Should pass extra kwargs to API."""
        provider._client.embeddings.create = AsyncMock(return_value=mock_response)

        await provider.embed(["Test"], user="user-123")

        call_args = provider._client.embeddings.create.call_args
        assert call_args.kwargs["user"] == "user-123"

    @pytest.mark.asyncio
    async def test_empty_response_handling(self, provider):
        """Should handle empty embeddings response."""
        mock_empty_response = MagicMock()
        mock_empty_response.data = []
        mock_empty_response.usage = MagicMock(total_tokens=0, prompt_tokens=0)

        provider._client.embeddings.create = AsyncMock(return_value=mock_empty_response)

        response = await provider.embed(["Test"])

        assert len(response.embeddings) == 0
        assert response.usage["total_tokens"] == 0

    @pytest.mark.asyncio
    async def test_response_without_usage(self, provider):
        """Should handle response without usage information."""
        mock_no_usage_response = MagicMock()
        mock_no_usage_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_no_usage_response.usage = None

        provider._client.embeddings.create = AsyncMock(return_value=mock_no_usage_response)

        response = await provider.embed(["Test"])

        assert response.usage is None
        assert len(response.embeddings) == 1

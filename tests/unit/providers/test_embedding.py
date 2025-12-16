"""Tests for embedding providers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ruche.infrastructure.providers.embedding import EmbeddingResponse, JinaEmbeddingProvider, MockEmbeddingProvider, OpenAIEmbeddingProvider


class TestMockEmbeddingProvider:
    """Tests for MockEmbeddingProvider."""

    @pytest.fixture
    def provider(self) -> MockEmbeddingProvider:
        """Create a mock provider."""
        return MockEmbeddingProvider(dimensions=128)

    @pytest.mark.asyncio
    async def test_embed_single_text(self, provider):
        """Should embed a single text."""
        embedding = await provider.embed_single("Hello world")

        assert isinstance(embedding, list)
        assert len(embedding) == 128
        assert all(isinstance(x, float) for x in embedding)

    @pytest.mark.asyncio
    async def test_embed_multiple_texts(self, provider):
        """Should embed multiple texts."""
        texts = ["Hello", "World", "Test"]
        response = await provider.embed(texts)

        assert isinstance(response, EmbeddingResponse)
        assert len(response.embeddings) == 3
        assert response.dimensions == 128

    @pytest.mark.asyncio
    async def test_embeddings_are_deterministic(self, provider):
        """Should return same embedding for same text."""
        text = "Test text"
        emb1 = await provider.embed_single(text)
        emb2 = await provider.embed_single(text)

        assert emb1 == emb2

    @pytest.mark.asyncio
    async def test_different_texts_different_embeddings(self, provider):
        """Should return different embeddings for different texts."""
        emb1 = await provider.embed_single("Hello")
        emb2 = await provider.embed_single("World")

        assert emb1 != emb2

    @pytest.mark.asyncio
    async def test_embeddings_are_normalized(self, provider):
        """Should return unit-length embeddings."""
        embedding = await provider.embed_single("Test")

        # Compute L2 norm
        magnitude = sum(x * x for x in embedding) ** 0.5
        assert abs(magnitude - 1.0) < 0.001  # Should be ~1.0

    @pytest.mark.asyncio
    async def test_provider_name(self, provider):
        """Should return provider name."""
        assert provider.provider_name == "mock"

    @pytest.mark.asyncio
    async def test_dimensions_property(self, provider):
        """Should return configured dimensions."""
        assert provider.dimensions == 128

    @pytest.mark.asyncio
    async def test_tracks_call_history(self, provider):
        """Should track call history."""
        await provider.embed(["Hello", "World"])

        assert len(provider.call_history) == 1
        assert provider.call_history[0]["texts"] == ["Hello", "World"]

    @pytest.mark.asyncio
    async def test_clear_history(self, provider):
        """Should clear call history."""
        await provider.embed(["Test"])
        assert len(provider.call_history) == 1

        provider.clear_history()
        assert len(provider.call_history) == 0

    @pytest.mark.asyncio
    async def test_usage_tracking(self, provider):
        """Should track token usage."""
        response = await provider.embed(["Hello world"])

        assert response.usage is not None
        assert "total_tokens" in response.usage


class TestJinaEmbeddingProvider:
    """Tests for JinaEmbeddingProvider."""

    @pytest.fixture
    def mock_response(self):
        """Create a mock API response."""
        return {
            "data": [
                {"embedding": [0.1] * 1024},
                {"embedding": [0.2] * 1024},
            ],
            "usage": {"total_tokens": 10, "prompt_tokens": 10},
        }

    @pytest.fixture
    def provider(self):
        """Create a Jina provider with mocked API key."""
        with patch.dict("os.environ", {"JINA_API_KEY": "test-key"}):
            return JinaEmbeddingProvider(dimensions=1024)

    @pytest.mark.asyncio
    async def test_provider_name(self, provider):
        """Should return provider name."""
        assert provider.provider_name == "jina"

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
        assert response.model == "jina-embeddings-v3"
        assert response.dimensions == 1024

    @pytest.mark.asyncio
    async def test_embed_with_task(self, provider, mock_response):
        """Should pass task parameter to API."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response

        provider._client.post = AsyncMock(return_value=mock_http_response)

        await provider.embed(["Test"], task="retrieval.query")

        # Verify the task was passed in the request
        call_args = provider._client.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["task"] == "retrieval.query"

    @pytest.mark.asyncio
    async def test_embed_query_uses_query_task(self, provider, mock_response):
        """Should use retrieval.query task for embed_query."""
        mock_response["data"] = [{"embedding": [0.1] * 1024}]
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response

        provider._client.post = AsyncMock(return_value=mock_http_response)

        await provider.embed_query("Search query")

        call_args = provider._client.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["task"] == "retrieval.query"

    @pytest.mark.asyncio
    async def test_embed_documents_uses_passage_task(self, provider, mock_response):
        """Should use retrieval.passage task for embed_documents."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response

        provider._client.post = AsyncMock(return_value=mock_http_response)

        await provider.embed_documents(["Doc 1", "Doc 2"])

        call_args = provider._client.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["task"] == "retrieval.passage"

    @pytest.mark.asyncio
    async def test_api_error_raises_exception(self, provider):
        """Should raise exception on API error."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 401
        mock_http_response.text = "Unauthorized"

        provider._client.post = AsyncMock(return_value=mock_http_response)

        with pytest.raises(RuntimeError, match="Jina API error"):
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

    @pytest.mark.asyncio
    async def test_metadata_includes_task(self, provider, mock_response):
        """Should include task in metadata."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response

        provider._client.post = AsyncMock(return_value=mock_http_response)

        response = await provider.embed(["Test", "Test2"], task="classification")

        assert response.metadata["task"] == "classification"

    def test_missing_api_key_raises_error(self):
        """Should raise error if API key not provided."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="JINA_API_KEY"):
                JinaEmbeddingProvider()


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

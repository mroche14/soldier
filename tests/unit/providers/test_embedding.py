"""Tests for embedding providers."""

import pytest

from soldier.providers.embedding import EmbeddingResponse, MockEmbeddingProvider


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

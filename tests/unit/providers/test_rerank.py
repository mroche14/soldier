"""Tests for rerank providers."""

import pytest

from soldier.providers.rerank import MockRerankProvider, RerankResponse


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

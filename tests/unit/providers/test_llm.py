"""Tests for LLM providers."""

import pytest

from soldier.providers.llm import LLMMessage, LLMResponse, MockLLMProvider


class TestMockLLMProvider:
    """Tests for MockLLMProvider."""

    @pytest.fixture
    def provider(self) -> MockLLMProvider:
        """Create a mock provider."""
        return MockLLMProvider(default_response="Test response")

    @pytest.mark.asyncio
    async def test_generate_returns_default_response(self, provider):
        """Should return default response."""
        messages = [LLMMessage(role="user", content="Hello")]
        response = await provider.generate(messages)

        assert isinstance(response, LLMResponse)
        assert response.content == "Test response"
        assert response.model == "mock-model"
        assert response.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_generate_custom_response(self, provider):
        """Should return custom response for matching content."""
        provider.set_response("What is 2+2?", "The answer is 4.")
        messages = [LLMMessage(role="user", content="What is 2+2?")]

        response = await provider.generate(messages)
        assert response.content == "The answer is 4."

    @pytest.mark.asyncio
    async def test_generate_tracks_call_history(self, provider):
        """Should track call history."""
        messages = [LLMMessage(role="user", content="Hello")]
        await provider.generate(messages, temperature=0.5)

        assert len(provider.call_history) == 1
        assert provider.call_history[0]["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_generate_stream(self, provider):
        """Should stream response in chunks."""
        provider = MockLLMProvider(
            default_response="Hello World!",
            stream_chunk_size=5,
        )
        messages = [LLMMessage(role="user", content="Hi")]

        chunks = []
        async for chunk in provider.generate_stream(messages):
            chunks.append(chunk)

        assert "".join(chunks) == "Hello World!"
        assert len(chunks) == 3  # "Hello", " Worl", "d!"

    @pytest.mark.asyncio
    async def test_count_tokens(self, provider):
        """Should estimate token count."""
        count = await provider.count_tokens("Hello world")
        assert count > 0

    @pytest.mark.asyncio
    async def test_provider_name(self, provider):
        """Should return provider name."""
        assert provider.provider_name == "mock"

    @pytest.mark.asyncio
    async def test_clear_history(self, provider):
        """Should clear call history."""
        messages = [LLMMessage(role="user", content="Hello")]
        await provider.generate(messages)
        assert len(provider.call_history) == 1

        provider.clear_history()
        assert len(provider.call_history) == 0

    @pytest.mark.asyncio
    async def test_usage_tracking(self, provider):
        """Should track token usage."""
        messages = [
            LLMMessage(role="system", content="You are helpful."),
            LLMMessage(role="user", content="Hello"),
        ]
        response = await provider.generate(messages)

        assert response.usage is not None
        assert "prompt_tokens" in response.usage
        assert "completion_tokens" in response.usage
        assert "total_tokens" in response.usage

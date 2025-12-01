"""Tests for LLM providers."""

import pytest
from pydantic import BaseModel

from soldier.providers.llm import (
    AuthenticationError,
    ContentFilterError,
    LLMMessage,
    LLMResponse,
    MockLLMProvider,
    ModelError,
    ProviderError,
    RateLimitError,
    TokenUsage,
)


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

    @pytest.mark.asyncio
    async def test_generate_structured_simple(self, provider):
        """Should generate structured output matching schema."""

        class Greeting(BaseModel):
            greeting: str
            language: str

        result, response = await provider.generate_structured(
            "Generate a greeting",
            Greeting,
        )

        assert isinstance(result, Greeting)
        assert result.greeting == "mock_greeting"
        assert result.language == "mock_language"
        assert isinstance(response, LLMResponse)
        assert response.content is not None

    @pytest.mark.asyncio
    async def test_generate_structured_with_int_field(self, provider):
        """Should generate int fields correctly."""

        class Counter(BaseModel):
            name: str
            count: int

        result, response = await provider.generate_structured(
            "Generate a counter",
            Counter,
        )

        assert isinstance(result, Counter)
        assert result.name == "mock_name"
        assert result.count == 42

    @pytest.mark.asyncio
    async def test_generate_structured_with_list_field(self, provider):
        """Should generate list fields correctly."""

        class Items(BaseModel):
            items: list[str]

        result, response = await provider.generate_structured(
            "Generate items",
            Items,
        )

        assert isinstance(result, Items)
        assert result.items == ["item1", "item2"]

    @pytest.mark.asyncio
    async def test_generate_structured_tracks_history(self, provider):
        """Should track generate_structured calls."""

        class Simple(BaseModel):
            value: str

        await provider.generate_structured(
            "Test prompt",
            Simple,
            system_prompt="Test system",
        )

        assert len(provider.call_history) == 1
        call = provider.call_history[0]
        assert call["method"] == "generate_structured"
        assert call["prompt"] == "Test prompt"
        assert call["schema"] == "Simple"
        assert call["system_prompt"] == "Test system"

    @pytest.mark.asyncio
    async def test_generate_structured_usage(self, provider):
        """Should return token usage in response."""

        class Simple(BaseModel):
            value: str

        result, response = await provider.generate_structured(
            "Test",
            Simple,
        )

        assert response.usage is not None
        assert isinstance(response.usage, TokenUsage)
        assert response.usage.total_tokens > 0


class TestErrorClasses:
    """Tests for error class hierarchy."""

    def test_authentication_error_is_provider_error(self):
        """AuthenticationError should inherit from ProviderError."""
        error = AuthenticationError("Invalid key")
        assert isinstance(error, ProviderError)
        assert str(error) == "Invalid key"

    def test_rate_limit_error_is_provider_error(self):
        """RateLimitError should inherit from ProviderError."""
        error = RateLimitError("Too many requests")
        assert isinstance(error, ProviderError)

    def test_model_error_is_provider_error(self):
        """ModelError should inherit from ProviderError."""
        error = ModelError("Model not found")
        assert isinstance(error, ProviderError)

    def test_content_filter_error_is_provider_error(self):
        """ContentFilterError should inherit from ProviderError."""
        error = ContentFilterError("Content blocked")
        assert isinstance(error, ProviderError)


class TestTokenUsage:
    """Tests for TokenUsage model."""

    def test_token_usage_creation(self):
        """Should create TokenUsage with all fields."""
        usage = TokenUsage(
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        )
        assert usage.prompt_tokens == 10
        assert usage.completion_tokens == 20
        assert usage.total_tokens == 30

    def test_token_usage_validation(self):
        """Should require all fields."""
        with pytest.raises(Exception):
            TokenUsage(prompt_tokens=10)  # Missing fields

# Provider Interface Contracts

**Feature**: 009-production-stores-providers
**Date**: 2025-11-29

## Overview

This document defines the interface contracts for AI provider implementations that must be validated by integration tests.

## LLMProvider Interface

```python
class LLMProvider(ABC):
    """Abstract interface for LLM text generation."""

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Return the model identifier."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        stop_sequences: list[str] | None = None,
    ) -> LLMResponse:
        """Generate text completion."""

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
        *,
        system_prompt: str | None = None,
        max_tokens: int = 1024,
    ) -> tuple[BaseModel, LLMResponse]:
        """Generate structured output matching schema."""
```

### LLMResponse Model

```python
class LLMResponse(BaseModel):
    content: str
    model: str
    usage: TokenUsage
    finish_reason: str
    raw_response: dict | None = None

class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
```

## EmbeddingProvider Interface

```python
class EmbeddingProvider(ABC):
    """Abstract interface for text embeddings."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return embedding vector dimensions."""

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Return the model identifier."""

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Generate embedding for single text."""

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
```

## Integration Test Contracts

### Anthropic Provider Tests

```python
@pytest.mark.integration
class TestAnthropicProvider:
    """Integration tests for Anthropic Claude API."""

    async def test_generate_returns_valid_response(self, provider):
        """Basic generation returns non-empty content."""
        response = await provider.generate("Say hello")
        assert response.content
        assert response.usage.total_tokens > 0

    async def test_generate_respects_max_tokens(self, provider):
        """Generation respects max_tokens limit."""
        response = await provider.generate(
            "Write a long story",
            max_tokens=50
        )
        assert response.usage.completion_tokens <= 60  # Allow small buffer

    async def test_generate_structured_returns_valid_model(self, provider):
        """Structured generation returns valid Pydantic model."""
        class Response(BaseModel):
            greeting: str
            language: str

        result, response = await provider.generate_structured(
            "Generate a greeting in Spanish",
            Response
        )
        assert isinstance(result, Response)
        assert result.greeting
        assert result.language

    async def test_generate_with_system_prompt(self, provider):
        """System prompt influences output."""
        response = await provider.generate(
            "What are you?",
            system_prompt="You are a helpful pirate assistant."
        )
        assert response.content

    async def test_handles_rate_limit(self, provider):
        """Rate limit errors are handled gracefully."""
        # This test validates error handling, may skip if rate limited
        ...
```

### OpenAI Provider Tests

```python
@pytest.mark.integration
class TestOpenAIProvider:
    """Integration tests for OpenAI API."""

    async def test_generate_returns_valid_response(self, provider):
        """Basic generation returns non-empty content."""
        response = await provider.generate("Say hello")
        assert response.content
        assert response.usage.total_tokens > 0

    async def test_generate_structured_returns_valid_model(self, provider):
        """Structured generation with JSON mode returns valid model."""
        class Response(BaseModel):
            greeting: str

        result, response = await provider.generate_structured(
            "Generate a greeting",
            Response
        )
        assert isinstance(result, Response)

    async def test_embed_returns_correct_dimensions(self, embedding_provider):
        """Embedding returns vector of correct dimensions."""
        embedding = await embedding_provider.embed("Hello world")
        assert len(embedding) == embedding_provider.dimensions
        assert all(isinstance(x, float) for x in embedding)

    async def test_embed_batch_returns_multiple_embeddings(self, embedding_provider):
        """Batch embedding returns correct number of vectors."""
        texts = ["Hello", "World", "Test"]
        embeddings = await embedding_provider.embed_batch(texts)
        assert len(embeddings) == len(texts)
        assert all(len(e) == embedding_provider.dimensions for e in embeddings)
```

## Test Fixture Contracts

### API Key Management

```python
@pytest.fixture
def anthropic_api_key() -> str:
    """Get Anthropic API key or skip test."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    return key

@pytest.fixture
def openai_api_key() -> str:
    """Get OpenAI API key or skip test."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        pytest.skip("OPENAI_API_KEY not set")
    return key
```

### Provider Initialization

```python
@pytest.fixture
async def anthropic_provider(anthropic_api_key) -> AnthropicProvider:
    """Create Anthropic provider with API key."""
    return AnthropicProvider(
        api_key=anthropic_api_key,
        model="claude-3-haiku-20240307"  # Use cheapest model for tests
    )

@pytest.fixture
async def openai_provider(openai_api_key) -> OpenAIProvider:
    """Create OpenAI provider with API key."""
    return OpenAIProvider(
        api_key=openai_api_key,
        model="gpt-4o-mini"  # Use cheapest model for tests
    )

@pytest.fixture
async def openai_embedding_provider(openai_api_key) -> OpenAIEmbeddingProvider:
    """Create OpenAI embedding provider."""
    return OpenAIEmbeddingProvider(
        api_key=openai_api_key,
        model="text-embedding-3-small"
    )
```

## Error Handling Contract

```python
class ProviderError(Exception):
    """Base exception for provider errors."""

class AuthenticationError(ProviderError):
    """Invalid or missing API key."""

class RateLimitError(ProviderError):
    """Rate limit exceeded."""

class ModelError(ProviderError):
    """Model not found or unavailable."""

class ContentFilterError(ProviderError):
    """Content blocked by safety filter."""
```

All provider methods must:
- Raise `AuthenticationError` on invalid API key (401)
- Raise `RateLimitError` on rate limit (429)
- Raise `ModelError` on invalid model (404)
- Raise `ContentFilterError` on safety blocks
- Include retry logic for transient errors (500, 503)
- Log API calls with latency metrics

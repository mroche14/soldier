# Provider Interface Contracts

**Date**: 2025-11-28
**Feature**: 003-core-abstractions

## Overview

This document defines the abstract interfaces for AI capability providers. Each interface is implemented as a Python ABC. All methods are async.

---

## LLMProvider

Interface for Large Language Model providers.

### Interface

```python
class LLMProvider(ABC):
    """Generate text responses via LLM."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'anthropic', 'openai', 'mock')."""

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
        """Generate text completion.

        Args:
            prompt: User prompt/message
            system_prompt: Optional system instructions
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0-1.0)
            stop_sequences: Sequences that stop generation

        Returns:
            LLMResponse with text, usage, model, finish_reason
        """

    @abstractmethod
    async def generate_structured[T: BaseModel](
        self,
        prompt: str,
        schema: type[T],
        *,
        system_prompt: str | None = None,
    ) -> T:
        """Generate structured output matching a Pydantic schema.

        Args:
            prompt: User prompt/message
            schema: Pydantic model class to parse into
            system_prompt: Optional system instructions

        Returns:
            Instance of schema class

        Raises:
            ValidationError: If response doesn't match schema
        """
```

### Response Models

```python
class LLMResponse(BaseModel):
    """Response from LLM generation."""
    text: str
    usage: TokenUsage
    model: str
    finish_reason: str  # "stop", "max_tokens", "content_filter"


class TokenUsage(BaseModel):
    """Token consumption for a generation."""
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
```

### Contract Tests

| Test | Action | Expected |
|------|--------|----------|
| `test_generate_basic` | Call generate with prompt | Non-empty text returned |
| `test_generate_with_system_prompt` | Call with system prompt | System prompt influences output |
| `test_generate_with_stop_sequences` | Call with stop sequences | Generation stops at sequence |
| `test_generate_max_tokens` | Call with low max_tokens | Output respects limit |
| `test_generate_temperature` | Call with temperature=0 | Deterministic output |
| `test_generate_structured` | Call with Pydantic schema | Valid schema instance returned |
| `test_generate_structured_invalid` | Schema mismatch | ValidationError raised |
| `test_token_usage_tracking` | Any generation | usage field populated correctly |
| `test_provider_name` | Access name property | Returns expected string |
| `test_fail_after_n` | Configure fail_after_n=3 | Calls 1-3 succeed, call 4 raises ProviderError |
| `test_error_rate` | Configure error_rate=1.0 | All calls raise ProviderError |

### MockLLMProvider Specifics

```python
class MockLLMProvider(LLMProvider):
    """Mock LLM for testing."""

    def __init__(
        self,
        default_response: str = "Mock response",
        responses: list[str] | None = None,  # Cycle through these
        token_ratio: float = 0.25,  # completion_tokens / prompt_tokens
        # Failure injection (from spec clarification)
        fail_after_n: int | None = None,  # Fail after N successful calls
        error_rate: float = 0.0,  # Probability of random failure (0.0-1.0)
    ):
        ...

    @property
    def call_history(self) -> list[dict]:
        """Access call history for assertions."""

    def reset(self) -> None:
        """Reset call count and history for test isolation."""
```

**Failure Injection** (per spec clarification):
- `fail_after_n=3`: First 3 calls succeed, 4th and subsequent raise `ProviderError`
- `error_rate=0.1`: 10% chance of `ProviderError` on each call
- Both can be combined for complex failure scenarios

---

## EmbeddingProvider

Interface for embedding models.

### Interface

```python
class EmbeddingProvider(ABC):
    """Convert text to vector embeddings."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'openai', 'cohere', 'mock')."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Vector dimensions for this model."""

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Embed a single text.

        Args:
            text: Text to embed

        Returns:
            Vector of floats with length == dimensions
        """

    @abstractmethod
    async def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 100,
    ) -> list[list[float]]:
        """Embed multiple texts efficiently.

        Args:
            texts: List of texts to embed
            batch_size: Processing batch size

        Returns:
            List of vectors, one per input text
        """
```

### Contract Tests

| Test | Action | Expected |
|------|--------|----------|
| `test_embed_single` | Call embed with text | Vector of correct dimensions |
| `test_embed_batch` | Call embed_batch with texts | Same number of vectors returned |
| `test_embed_batch_empty` | Call with empty list | Empty list returned |
| `test_dimensions_property` | Access dimensions | Positive integer |
| `test_embedding_consistency` | Embed same text twice | Identical vectors |
| `test_embedding_similarity` | Embed similar texts | High cosine similarity |
| `test_provider_name` | Access name property | Returns expected string |

### MockEmbeddingProvider Specifics

```python
class MockEmbeddingProvider(EmbeddingProvider):
    """Mock embedding provider for testing."""

    def __init__(
        self,
        dimensions: int = 384,
        deterministic: bool = True,  # Same text -> same vector
        # Failure injection (from spec clarification)
        fail_after_n: int | None = None,
        error_rate: float = 0.0,
    ):
        ...
```

**Deterministic Behavior**: When `deterministic=True`, the mock generates vectors based on text hash, ensuring the same text always produces the same embedding. This enables reliable similarity testing.

**Failure Injection**: Same as MockLLMProvider - supports `fail_after_n` and `error_rate` for testing error handling.

---

## RerankProvider

Interface for reranking models.

### Interface

```python
class RerankProvider(ABC):
    """Re-order search results by relevance."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'cohere', 'cross_encoder', 'mock')."""

    @abstractmethod
    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None,
    ) -> list[RerankResult]:
        """Rerank documents by relevance to query.

        Args:
            query: Search query
            documents: Documents to rerank
            top_k: Return only top K results (None = all)

        Returns:
            Results sorted by relevance score (highest first)
        """
```

### Response Model

```python
class RerankResult(BaseModel):
    """Result from reranking."""
    index: int = Field(ge=0)  # Original index in documents list
    score: float = Field(ge=0, le=1)  # Relevance score
    document: str  # The document text
```

### Contract Tests

| Test | Action | Expected |
|------|--------|----------|
| `test_rerank_basic` | Call rerank with query and docs | Results sorted by score |
| `test_rerank_top_k` | Call with top_k=3 | At most 3 results |
| `test_rerank_empty_docs` | Call with empty documents | Empty list returned |
| `test_rerank_single_doc` | Call with one document | One result with score |
| `test_rerank_preserves_index` | Check result indices | Match original positions |
| `test_rerank_score_range` | Check scores | All between 0 and 1 |
| `test_provider_name` | Access name property | Returns expected string |

### MockRerankProvider Specifics

```python
class MockRerankProvider(RerankProvider):
    """Mock rerank provider for testing."""

    def __init__(
        self,
        score_strategy: str = "position",  # "position", "random", "fixed"
        fixed_scores: list[float] | None = None,
        # Failure injection (from spec clarification)
        fail_after_n: int | None = None,
        error_rate: float = 0.0,
    ):
        ...
```

**Score Strategies**:
- `position`: Score = 1.0 - (index * 0.1), simulating relevance decay
- `random`: Random scores for each rerank call
- `fixed`: Use provided fixed_scores list

**Failure Injection**: Same as MockLLMProvider - supports `fail_after_n` and `error_rate` for testing error handling.

---

## Provider Factory

Factory functions for creating providers from configuration.

### Interface

```python
def create_llm_provider(config: LLMProviderConfig) -> LLMProvider:
    """Create LLM provider from configuration.

    Args:
        config: Provider configuration with type, model, etc.

    Returns:
        Configured LLMProvider instance

    Raises:
        ValueError: If provider type is unknown
    """


def create_embedding_provider(config: EmbeddingProviderConfig) -> EmbeddingProvider:
    """Create embedding provider from configuration."""


def create_rerank_provider(config: RerankProviderConfig) -> RerankProvider:
    """Create rerank provider from configuration."""
```

### Configuration Models

```python
class LLMProviderConfig(BaseModel):
    """Configuration for LLM provider."""
    provider: str  # "mock", "anthropic", "openai"
    model: str | None = None
    api_key: SecretStr | None = None
    # Mock-specific
    default_response: str | None = None


class EmbeddingProviderConfig(BaseModel):
    """Configuration for embedding provider."""
    provider: str  # "mock", "openai", "cohere"
    model: str | None = None
    api_key: SecretStr | None = None
    # Mock-specific
    dimensions: int = 384


class RerankProviderConfig(BaseModel):
    """Configuration for rerank provider."""
    provider: str  # "mock", "cohere", "cross_encoder"
    model: str | None = None
    api_key: SecretStr | None = None
    # Mock-specific
    score_strategy: str = "position"
```

### Factory Tests

| Test | Action | Expected |
|------|--------|----------|
| `test_create_mock_llm` | Create with provider="mock" | MockLLMProvider instance |
| `test_create_mock_embedding` | Create with provider="mock" | MockEmbeddingProvider instance |
| `test_create_mock_rerank` | Create with provider="mock" | MockRerankProvider instance |
| `test_unknown_provider` | Create with provider="unknown" | ValueError raised |
| `test_config_passthrough` | Create with config options | Options applied to provider |

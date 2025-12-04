"""AI provider configuration models."""

from typing import Literal

from pydantic import BaseModel, Field, SecretStr

# Provider types for LLM
# Model string format: "{aggregator}/{provider}/{model}" or "{provider}/{model}"
# Examples:
#   - "openrouter/anthropic/claude-3-haiku-20240307" -> OpenRouter
#   - "anthropic/claude-3-haiku-20240307" -> Direct Anthropic
#   - "openai/gpt-4o-mini" -> Direct OpenAI
LLMProviderType = Literal[
    "openrouter",   # OpenRouter aggregator (primary)
    "anthropic",    # Direct Anthropic API (fallback)
    "openai",       # Direct OpenAI API (fallback)
    "bedrock",      # AWS Bedrock
    "vertex",       # Google Vertex AI
    "ollama",       # Local Ollama
    "mock",         # Testing
]
EmbeddingProviderType = Literal["openai", "cohere", "voyage", "jina", "sentence_transformers", "mock"]
RerankProviderType = Literal["cohere", "voyage", "jina", "cross_encoder", "mock"]


class LLMProviderConfig(BaseModel):
    """Configuration for an LLM provider.

    Model string format determines the provider:
    - "openrouter/anthropic/claude-3-haiku-20240307" -> uses OpenRouter
    - "anthropic/claude-3-haiku-20240307" -> uses direct Anthropic API
    - "openai/gpt-4o-mini" -> uses direct OpenAI API

    The provider field can be set explicitly or auto-detected from model string.
    """

    model: str = Field(
        ...,  # Required - full model identifier
        description="Full model identifier (e.g., 'openrouter/anthropic/claude-3-haiku-20240307')",
    )
    api_key: SecretStr | None = Field(
        default=None,
        description="API key (prefer env var: OPENROUTER_API_KEY, ANTHROPIC_API_KEY, etc.)",
    )
    api_key_env: str | None = Field(
        default=None,
        description="Environment variable name for API key",
    )
    base_url: str | None = Field(
        default=None,
        description="Custom API base URL (overrides default)",
    )
    max_tokens: int = Field(
        default=4096,
        gt=0,
        description="Default max tokens",
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Default temperature",
    )
    timeout: int = Field(
        default=60,
        gt=0,
        description="Request timeout in seconds",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        description="Max retries for transient errors",
    )

    def get_provider_type(self) -> str:
        """Detect provider type from model string.

        Returns:
            Provider type based on model string prefix
        """
        parts = self.model.split("/")
        if len(parts) >= 3 and parts[0] == "openrouter":
            return "openrouter"
        elif len(parts) >= 2:
            return parts[0]  # anthropic, openai, etc.
        return "unknown"

    def get_model_for_api(self) -> str:
        """Get model identifier to send to the API.

        For OpenRouter: strips the 'openrouter/' prefix
        For direct providers: returns as-is

        Returns:
            Model identifier for API calls
        """
        parts = self.model.split("/")
        if len(parts) >= 3 and parts[0] == "openrouter":
            # OpenRouter format: openrouter/anthropic/claude-3-haiku -> anthropic/claude-3-haiku
            return "/".join(parts[1:])
        return self.model


class EmbeddingProviderConfig(BaseModel):
    """Configuration for an embedding provider."""

    provider: EmbeddingProviderType = Field(
        default="openai",
        description="Provider type",
    )
    model: str = Field(
        default="text-embedding-3-small",
        description="Model identifier",
    )
    api_key: SecretStr | None = Field(
        default=None,
        description="API key (prefer env var)",
    )
    dimensions: int = Field(
        default=1536,
        gt=0,
        description="Embedding dimensions",
    )
    batch_size: int = Field(
        default=100,
        gt=0,
        description="Batch size for embedding",
    )


class RerankProviderConfig(BaseModel):
    """Configuration for a rerank provider."""

    provider: RerankProviderType = Field(
        default="cohere",
        description="Provider type",
    )
    model: str = Field(
        default="rerank-english-v3.0",
        description="Model identifier",
    )
    api_key: SecretStr | None = Field(
        default=None,
        description="API key (prefer env var)",
    )
    top_k: int = Field(
        default=10,
        gt=0,
        description="Number of results to return",
    )


class ProvidersConfig(BaseModel):
    """Configuration for AI providers.

    Note: LLM models are configured directly on each pipeline step
    using full model strings (e.g., 'openrouter/anthropic/claude-3-haiku-20240307').
    This config only handles embedding and rerank providers.
    """

    default_embedding: str = Field(
        default="default",
        description="Default embedding provider name",
    )
    default_rerank: str = Field(
        default="default",
        description="Default rerank provider name",
    )
    embedding: dict[str, EmbeddingProviderConfig] = Field(
        default_factory=dict,
        description="Named embedding providers",
    )
    rerank: dict[str, RerankProviderConfig] = Field(
        default_factory=dict,
        description="Named rerank providers",
    )

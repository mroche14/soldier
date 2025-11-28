"""AI provider configuration models."""

from typing import Literal

from pydantic import BaseModel, Field, SecretStr

LLMProviderType = Literal["anthropic", "openai", "bedrock", "vertex", "ollama", "mock"]
EmbeddingProviderType = Literal["openai", "cohere", "voyage", "sentence_transformers", "mock"]
RerankProviderType = Literal["cohere", "voyage", "cross_encoder", "mock"]


class LLMProviderConfig(BaseModel):
    """Configuration for an LLM provider."""

    provider: LLMProviderType = Field(
        default="anthropic",
        description="Provider type",
    )
    model: str = Field(
        default="claude-3-haiku-20240307",
        description="Model identifier",
    )
    api_key: SecretStr | None = Field(
        default=None,
        description="API key (prefer env var)",
    )
    base_url: str | None = Field(
        default=None,
        description="Custom API base URL",
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
    """Configuration for AI providers."""

    default_llm: str = Field(
        default="haiku",
        description="Default LLM provider name",
    )
    default_embedding: str = Field(
        default="default",
        description="Default embedding provider name",
    )
    default_rerank: str = Field(
        default="default",
        description="Default rerank provider name",
    )
    llm: dict[str, LLMProviderConfig] = Field(
        default_factory=dict,
        description="Named LLM providers",
    )
    embedding: dict[str, EmbeddingProviderConfig] = Field(
        default_factory=dict,
        description="Named embedding providers",
    )
    rerank: dict[str, RerankProviderConfig] = Field(
        default_factory=dict,
        description="Named rerank providers",
    )

"""Turn pipeline configuration models."""

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from soldier.config.models.selection import SelectionConfig

ExtractionMode = Literal["llm", "embedding", "hybrid"]
ProviderSortMode = Literal["price", "latency", "throughput"]


class OpenRouterProviderConfig(BaseModel):
    """OpenRouter-specific provider routing configuration.

    Controls how OpenRouter routes requests to underlying providers.
    See: https://openrouter.ai/docs#provider-routing
    """

    provider_order: list[str] | None = Field(
        default=None,
        description="Ordered list of provider names to try (e.g., ['Hyperbolic', 'Together'])",
    )
    provider_sort: ProviderSortMode | None = Field(
        default=None,
        description="Sort providers by: 'price', 'latency', or 'throughput'",
    )
    allow_fallbacks: bool = Field(
        default=True,
        description="Allow fallback to other providers if specified ones fail",
    )
    ignore_providers: list[str] = Field(
        default_factory=list,
        description="List of provider names to exclude from routing",
    )

    def to_request_params(self) -> dict | None:
        """Convert to OpenRouter request_params format."""
        provider = {}

        if self.provider_order:
            provider["order"] = self.provider_order
        if self.provider_sort:
            provider["sort"] = self.provider_sort
        if self.ignore_providers:
            provider["ignore"] = self.ignore_providers
        # Only include allow_fallbacks if explicitly set to False
        # (True is the default on OpenRouter side)
        if not self.allow_fallbacks:
            provider["allow_fallbacks"] = False

        if provider:
            return {"provider": provider}
        return None

    def has_config(self) -> bool:
        """Check if any provider routing config is set."""
        return bool(
            self.provider_order
            or self.provider_sort
            or self.ignore_providers
            or not self.allow_fallbacks
        )


class OpenRouterConfigMixin(BaseModel):
    """Mixin for step configs that support OpenRouter provider routing.

    Allows flat config structure:
        [pipeline.context_extraction]
        provider_order = ["cerebras", "groq"]
        provider_sort = "latency"

    Instead of nested:
        [pipeline.context_extraction.openrouter]
        provider_order = ["cerebras", "groq"]
    """

    # Flat fields for convenience
    provider_order: list[str] | None = Field(
        default=None,
        description="OpenRouter: ordered list of provider names to try",
    )
    provider_sort: ProviderSortMode | None = Field(
        default=None,
        description="OpenRouter: sort providers by 'price', 'latency', or 'throughput'",
    )
    allow_fallbacks: bool = Field(
        default=True,
        description="OpenRouter: allow fallback to other providers if specified ones fail",
    )
    ignore_providers: list[str] = Field(
        default_factory=list,
        description="OpenRouter: list of provider names to exclude from routing",
    )

    # Nested config (populated from flat fields or directly)
    openrouter: OpenRouterProviderConfig | None = Field(
        default=None,
        description="OpenRouter-specific provider routing (only applies to openrouter/* models)",
    )

    @model_validator(mode="before")
    @classmethod
    def build_openrouter_config(cls, data: Any) -> Any:
        """Build openrouter config from flat fields if not explicitly provided."""
        if not isinstance(data, dict):
            return data

        # If openrouter is already set as a nested dict, leave it alone
        if data.get("openrouter") is not None:
            return data

        # Check if any flat OpenRouter fields are set
        provider_order = data.get("provider_order")
        provider_sort = data.get("provider_sort")
        allow_fallbacks = data.get("allow_fallbacks", True)
        ignore_providers = data.get("ignore_providers", [])

        # Build openrouter config from flat fields if any are set
        if provider_order or provider_sort or ignore_providers or not allow_fallbacks:
            data["openrouter"] = {
                "provider_order": provider_order,
                "provider_sort": provider_sort,
                "allow_fallbacks": allow_fallbacks,
                "ignore_providers": ignore_providers,
            }

        return data


class ContextExtractionConfig(OpenRouterConfigMixin):
    """Context extraction step configuration."""

    enabled: bool = Field(default=True, description="Enable this step")
    mode: ExtractionMode = Field(default="llm", description="Extraction mode")
    model: str = Field(
        default="openrouter/anthropic/claude-3-haiku-20240307",
        description="Full model identifier (e.g., 'openrouter/anthropic/claude-3-haiku-20240307')",
    )
    fallback_models: list[str] = Field(
        default_factory=list,
        description="Fallback models if primary fails",
    )
    history_turns: int = Field(
        default=5,
        ge=0,
        description="Number of history turns to include",
    )


class RetrievalConfig(BaseModel):
    """Retrieval step configuration."""

    enabled: bool = Field(default=True, description="Enable this step")
    embedding_provider: str = Field(
        default="default",
        description="Embedding provider name",
    )
    max_k: int = Field(
        default=30,
        gt=0,
        description="Maximum candidates to retrieve",
    )
    rule_selection: SelectionConfig = Field(
        default_factory=SelectionConfig,
        description="Rule selection strategy",
    )
    scenario_selection: SelectionConfig = Field(
        default_factory=SelectionConfig,
        description="Scenario selection strategy",
    )
    memory_selection: SelectionConfig = Field(
        default_factory=SelectionConfig,
        description="Memory selection strategy",
    )


class RerankingConfig(BaseModel):
    """Reranking step configuration."""

    enabled: bool = Field(default=True, description="Enable this step")
    rerank_provider: str = Field(
        default="default",
        description="Rerank provider name",
    )
    top_k: int = Field(
        default=10,
        gt=0,
        description="Number of results after reranking",
    )


class RuleFilteringConfig(OpenRouterConfigMixin):
    """Rule filtering step configuration."""

    enabled: bool = Field(default=True, description="Enable this step")
    model: str = Field(
        default="openrouter/anthropic/claude-3-haiku-20240307",
        description="Full model identifier",
    )
    fallback_models: list[str] = Field(
        default_factory=list,
        description="Fallback models if primary fails",
    )
    batch_size: int = Field(
        default=5,
        gt=0,
        description="Batch size for filtering",
    )


class ScenarioFilteringConfig(OpenRouterConfigMixin):
    """Scenario filtering step configuration."""

    enabled: bool = Field(default=True, description="Enable this step")
    model: str = Field(
        default="openrouter/anthropic/claude-3-haiku-20240307",
        description="Full model identifier",
    )
    fallback_models: list[str] = Field(
        default_factory=list,
        description="Fallback models if primary fails",
    )
    relocalize_on_inconsistent: bool = Field(
        default=True,
        description="Attempt relocalization on inconsistent state",
    )
    max_loop_count: int = Field(
        default=3,
        ge=1,
        description="Max times to visit same step before loop detection",
    )


class ToolExecutionConfig(BaseModel):
    """Tool execution step configuration."""

    enabled: bool = Field(default=True, description="Enable this step")
    timeout_ms: int = Field(
        default=5000,
        gt=0,
        description="Timeout per tool execution",
    )
    max_parallel: int = Field(
        default=5,
        ge=1,
        description="Max tools to execute in parallel",
    )
    fail_fast: bool = Field(
        default=False,
        description="Stop on first tool failure",
    )


# Keep LLMFilteringConfig as alias for backwards compatibility
LLMFilteringConfig = RuleFilteringConfig


class GenerationConfig(OpenRouterConfigMixin):
    """Response generation step configuration."""

    enabled: bool = Field(default=True, description="Enable this step")
    model: str = Field(
        default="openrouter/anthropic/claude-sonnet-4-5-20250514",
        description="Full model identifier",
    )
    fallback_models: list[str] = Field(
        default_factory=list,
        description="Fallback models if primary fails",
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Generation temperature",
    )
    max_tokens: int = Field(
        default=1024,
        gt=0,
        description="Max tokens for response",
    )


class EnforcementConfig(BaseModel):
    """Enforcement step configuration."""

    enabled: bool = Field(default=True, description="Enable this step")
    self_critique_enabled: bool = Field(
        default=False,
        description="Enable self-critique",
    )
    max_retries: int = Field(
        default=2,
        ge=0,
        description="Max generation retries",
    )


class EntityExtractionConfig(OpenRouterConfigMixin):
    """Entity extraction configuration."""

    enabled: bool = Field(default=True, description="Enable entity extraction")
    model: str = Field(
        default="openrouter/anthropic/claude-3-haiku-20240307",
        description="Full model identifier",
    )
    fallback_models: list[str] = Field(
        default_factory=list,
        description="Fallback models if primary fails",
    )
    max_tokens: int = Field(default=1024, gt=0, description="Max tokens")
    temperature: float = Field(
        default=0.3, ge=0.0, le=2.0, description="LLM temperature"
    )
    batch_size: int = Field(default=10, gt=0, description="Batch size")
    timeout_ms: int = Field(default=2000, gt=0, description="Timeout in ms")
    min_confidence: Literal["high", "medium", "low"] = Field(
        default="medium", description="Minimum confidence"
    )


class EntityDeduplicationConfig(BaseModel):
    """Entity deduplication configuration."""

    exact_match_enabled: bool = Field(
        default=True, description="Enable exact match stage"
    )
    fuzzy_match_enabled: bool = Field(
        default=True, description="Enable fuzzy match stage"
    )
    fuzzy_threshold: float = Field(
        default=0.85, ge=0.0, le=1.0, description="Fuzzy match threshold"
    )
    embedding_match_enabled: bool = Field(
        default=True, description="Enable embedding match stage"
    )
    embedding_threshold: float = Field(
        default=0.80, ge=0.0, le=1.0, description="Embedding match threshold"
    )
    rule_based_enabled: bool = Field(
        default=True, description="Enable rule-based matching"
    )


class WindowSummarizationConfig(OpenRouterConfigMixin):
    """Window summarization configuration."""

    turns_per_summary: int = Field(
        default=20, gt=0, description="Turns per summary window"
    )
    model: str = Field(
        default="openrouter/anthropic/claude-3-haiku-20240307",
        description="Full model identifier",
    )
    fallback_models: list[str] = Field(
        default_factory=list,
        description="Fallback models if primary fails",
    )
    max_tokens: int = Field(default=256, gt=0, description="Max tokens")
    temperature: float = Field(default=0.5, ge=0.0, le=2.0, description="Temperature")


class MetaSummarizationConfig(OpenRouterConfigMixin):
    """Meta-summarization configuration."""

    summaries_per_meta: int = Field(
        default=5, gt=0, description="Summaries per meta-summary"
    )
    enabled_at_turn_count: int = Field(
        default=100, gt=0, description="Enable meta-summaries at turn count"
    )
    model: str = Field(
        default="openrouter/anthropic/claude-3-haiku-20240307",
        description="Full model identifier",
    )
    fallback_models: list[str] = Field(
        default_factory=list,
        description="Fallback models if primary fails",
    )
    max_tokens: int = Field(default=512, gt=0, description="Max tokens")
    temperature: float = Field(default=0.5, ge=0.0, le=2.0, description="Temperature")


class SummarizationConfig(BaseModel):
    """Summarization configuration."""

    enabled: bool = Field(default=True, description="Enable summarization")
    window: WindowSummarizationConfig = Field(
        default_factory=WindowSummarizationConfig,
        description="Window summarization",
    )
    meta: MetaSummarizationConfig = Field(
        default_factory=MetaSummarizationConfig,
        description="Meta-summarization",
    )


class MemoryIngestionConfig(BaseModel):
    """Memory ingestion system configuration."""

    enabled: bool = Field(default=True, description="Enable memory ingestion")
    embedding_enabled: bool = Field(
        default=True, description="Generate embeddings during ingestion"
    )
    entity_extraction_enabled: bool = Field(
        default=True, description="Enable entity extraction"
    )
    summarization_enabled: bool = Field(
        default=True, description="Enable summarization"
    )
    async_extraction: bool = Field(
        default=True, description="Run extraction asynchronously"
    )
    async_summarization: bool = Field(
        default=True, description="Run summarization asynchronously"
    )
    queue_backend: Literal["redis", "inmemory"] = Field(
        default="inmemory", description="Task queue backend"
    )
    max_ingestion_latency_ms: int = Field(
        default=500, gt=0, description="Max ingestion latency target"
    )
    entity_extraction: EntityExtractionConfig = Field(
        default_factory=EntityExtractionConfig,
        description="Entity extraction config",
    )
    deduplication: EntityDeduplicationConfig = Field(
        default_factory=EntityDeduplicationConfig,
        description="Deduplication config",
    )
    summarization: SummarizationConfig = Field(
        default_factory=SummarizationConfig,
        description="Summarization config",
    )


class PipelineConfig(BaseModel):
    """Configuration for the turn pipeline."""

    context_extraction: ContextExtractionConfig = Field(
        default_factory=ContextExtractionConfig,
        description="Context extraction step",
    )
    retrieval: RetrievalConfig = Field(
        default_factory=RetrievalConfig,
        description="Retrieval step",
    )
    reranking: RerankingConfig = Field(
        default_factory=RerankingConfig,
        description="Reranking step",
    )
    rule_filtering: RuleFilteringConfig = Field(
        default_factory=RuleFilteringConfig,
        description="Rule filtering step",
    )
    scenario_filtering: ScenarioFilteringConfig = Field(
        default_factory=ScenarioFilteringConfig,
        description="Scenario filtering step",
    )
    tool_execution: ToolExecutionConfig = Field(
        default_factory=ToolExecutionConfig,
        description="Tool execution step",
    )
    generation: GenerationConfig = Field(
        default_factory=GenerationConfig,
        description="Response generation step",
    )
    enforcement: EnforcementConfig = Field(
        default_factory=EnforcementConfig,
        description="Enforcement step",
    )
    memory_ingestion: MemoryIngestionConfig = Field(
        default_factory=MemoryIngestionConfig,
        description="Memory ingestion configuration",
    )

    # Backwards compatibility alias
    @property
    def llm_filtering(self) -> RuleFilteringConfig:
        """Alias for rule_filtering for backwards compatibility."""
        return self.rule_filtering

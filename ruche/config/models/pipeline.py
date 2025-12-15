"""Turn pipeline configuration models."""

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from ruche.config.models.selection import SelectionConfig

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


class SituationSensorConfig(OpenRouterConfigMixin):
    """Situational sensor step configuration (Phase 2).

    Replaces basic context extraction with schema-aware,
    glossary-aware extraction that produces SituationSnapshot.
    """

    enabled: bool = Field(default=True, description="Enable this step")
    model: str = Field(
        default="openrouter/openai/gpt-oss-120b",
        description="Full model identifier",
    )
    fallback_models: list[str] = Field(
        default_factory=lambda: ["anthropic/claude-3-5-haiku-20241022"],
        description="Fallback models if primary fails",
    )
    temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description="Temperature (0.0 for deterministic extraction)",
    )
    max_tokens: int = Field(
        default=800,
        gt=0,
        description="Maximum tokens to generate",
    )
    history_turns: int = Field(
        default=5,
        ge=0,
        description="Number of history turns to include",
    )
    include_glossary: bool = Field(
        default=True,
        description="Include domain glossary in prompt",
    )
    include_schema_mask: bool = Field(
        default=True,
        description="Include customer data schema mask in prompt",
    )


class HybridRetrievalConfig(BaseModel):
    """Configuration for hybrid (vector + BM25) retrieval."""

    enabled: bool = Field(default=False, description="Enable hybrid retrieval")
    vector_weight: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Weight for embedding similarity (0-1)",
    )
    bm25_weight: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Weight for BM25 lexical match (0-1)",
    )
    normalization: Literal["min_max", "z_score", "softmax"] = Field(
        default="min_max",
        description="Score normalization method",
    )


class RerankingConfig(BaseModel):
    """Reranking step configuration."""

    enabled: bool = Field(default=False, description="Enable this step")
    rerank_provider: str = Field(
        default="default",
        description="Rerank provider name",
    )
    top_k: int = Field(
        default=10,
        gt=0,
        description="Number of results after reranking",
    )


class RetrievalConfig(BaseModel):
    """Retrieval step configuration with per-object-type reranking and hybrid search."""

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

    # Selection strategies per object type
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
    intent_selection: SelectionConfig = Field(
        default_factory=SelectionConfig,
        description="Intent selection strategy",
    )

    # Optional reranking per object type
    rule_reranking: RerankingConfig | None = Field(
        default=None,
        description="Optional reranking for rules",
    )
    scenario_reranking: RerankingConfig | None = Field(
        default=None,
        description="Optional reranking for scenarios",
    )
    memory_reranking: RerankingConfig | None = Field(
        default=None,
        description="Optional reranking for memory",
    )
    intent_reranking: RerankingConfig | None = Field(
        default=None,
        description="Optional reranking for intents",
    )

    # Hybrid retrieval per object type
    rule_hybrid: HybridRetrievalConfig = Field(
        default_factory=HybridRetrievalConfig,
        description="Hybrid retrieval config for rules",
    )
    scenario_hybrid: HybridRetrievalConfig = Field(
        default_factory=HybridRetrievalConfig,
        description="Hybrid retrieval config for scenarios",
    )
    memory_hybrid: HybridRetrievalConfig = Field(
        default_factory=HybridRetrievalConfig,
        description="Hybrid retrieval config for memory",
    )
    intent_hybrid: HybridRetrievalConfig = Field(
        default_factory=HybridRetrievalConfig,
        description="Hybrid retrieval config for intents",
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


class RelationshipExpansionConfig(BaseModel):
    """Relationship expansion configuration."""

    enabled: bool = Field(default=True, description="Enable relationship expansion")
    max_depth: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Maximum relationship chain depth",
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


class ScenarioOrchestrationConfig(BaseModel):
    """Scenario orchestration configuration (Phase 6)."""

    enabled: bool = Field(default=True, description="Enable scenario orchestration")
    max_loop_count: int = Field(
        default=3, ge=1, description="Maximum visits to a step before relocalization"
    )
    max_simultaneous_scenarios: int = Field(
        default=5, ge=1, le=20, description="Maximum active scenarios per session"
    )
    block_on_missing_hard_fields: bool = Field(
        default=True,
        description="Block scenario entry when hard requirements are missing",
    )
    enable_step_skipping: bool = Field(
        default=True, description="Enable automatic step skipping with available data"
    )
    enable_multi_scenario: bool = Field(
        default=True, description="Allow multiple active scenarios"
    )


class InterlocutorDataUpdateConfig(BaseModel):
    """Customer data update step configuration (Phase 3)."""

    enabled: bool = Field(default=True, description="Enable this step")
    validation_mode: Literal["strict", "warn", "disabled"] = Field(
        default="strict",
        description="Validation behavior: strict (reject invalid), warn (log only), disabled",
    )
    max_history_entries: int = Field(
        default=10,
        ge=0,
        description="Maximum history entries per variable",
    )


class TurnContextConfig(BaseModel):
    """Turn context loading configuration (Phase 1)."""

    load_glossary: bool = Field(
        default=True,
        description="Load glossary items for the turn",
    )
    load_customer_data_schema: bool = Field(
        default=True,
        description="Load customer data schema for the turn",
    )
    enable_scenario_reconciliation: bool = Field(
        default=True,
        description="Enable scenario migration reconciliation",
    )


class ToolExecutionConfig(BaseModel):
    """Tool execution step configuration (Phase 7)."""

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
    enable_before_step: bool = Field(
        default=True,
        description="Enable BEFORE_STEP tool execution",
    )
    enable_during_step: bool = Field(
        default=True,
        description="Enable DURING_STEP tool execution",
    )
    enable_after_step: bool = Field(
        default=True,
        description="Enable AFTER_STEP tool execution",
    )


# Keep LLMFilteringConfig as alias for backwards compatibility
LLMFilteringConfig = RuleFilteringConfig


class ResponsePlanningConfig(BaseModel):
    """Response planning step configuration (Phase 8)."""

    enabled: bool = Field(default=True, description="Enable this step")
    prioritize_escalation: bool = Field(
        default=True,
        description="Escalation rules override all other types",
    )
    merge_templates: bool = Field(
        default=True,
        description="Combine templates from multiple scenarios",
    )
    extract_must_include: bool = Field(
        default=True,
        description="Extract must_include constraints from rules",
    )
    extract_must_avoid: bool = Field(
        default=True,
        description="Extract must_avoid constraints from rules",
    )
    sort_by_urgency: bool = Field(
        default=True,
        description="Sort contributions by urgency before scenario order",
    )


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
    """Enforcement step configuration.

    Supports two-lane enforcement:
    - Lane 1 (Deterministic): Rules with enforcement_expression use simpleeval
    - Lane 2 (Subjective): Rules without expression use LLM-as-Judge
    """

    enabled: bool = Field(default=True, description="Enable this step")
    max_retries: int = Field(
        default=1,
        ge=0,
        le=3,
        description="Max regeneration attempts on violation",
    )

    # Lane 1: Deterministic enforcement (simpleeval)
    deterministic_enabled: bool = Field(
        default=True,
        description="Enable expression-based enforcement for rules with enforcement_expression",
    )

    # Lane 2: LLM-as-Judge (subjective rules)
    llm_judge_enabled: bool = Field(
        default=True,
        description="Enable LLM judgment for subjective rules without enforcement_expression",
    )
    llm_judge_models: list[str] = Field(
        default_factory=lambda: ["openrouter/anthropic/claude-3-haiku-20240307"],
        description="Models for LLM-as-Judge subjective enforcement",
    )

    # Always-enforce GLOBAL constraints
    always_enforce_global: bool = Field(
        default=True,
        description="Always fetch and enforce GLOBAL hard constraints, even if not matched",
    )

    # Legacy field for backwards compatibility
    self_critique_enabled: bool = Field(
        default=False,
        description="Deprecated: Use llm_judge_enabled instead",
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

    turn_context: TurnContextConfig = Field(
        default_factory=TurnContextConfig,
        description="Turn context loading (Phase 1)",
    )
    context_extraction: ContextExtractionConfig = Field(
        default_factory=ContextExtractionConfig,
        description="Context extraction step",
    )
    situation_sensor: SituationSensorConfig = Field(
        default_factory=SituationSensorConfig,
        description="Situational sensor step (Phase 2)",
    )
    customer_data_update: InterlocutorDataUpdateConfig = Field(
        default_factory=InterlocutorDataUpdateConfig,
        description="Customer data update step (Phase 3)",
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
    relationship_expansion: RelationshipExpansionConfig = Field(
        default_factory=RelationshipExpansionConfig,
        description="Relationship expansion configuration",
    )
    scenario_filtering: ScenarioFilteringConfig = Field(
        default_factory=ScenarioFilteringConfig,
        description="Scenario filtering step",
    )
    scenario_orchestration: ScenarioOrchestrationConfig = Field(
        default_factory=ScenarioOrchestrationConfig,
        description="Scenario orchestration step (Phase 6)",
    )
    tool_execution: ToolExecutionConfig = Field(
        default_factory=ToolExecutionConfig,
        description="Tool execution step",
    )
    response_planning: ResponsePlanningConfig = Field(
        default_factory=ResponsePlanningConfig,
        description="Response planning step (Phase 8)",
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

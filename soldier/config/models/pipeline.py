"""Turn pipeline configuration models."""

from typing import Literal

from pydantic import BaseModel, Field

from soldier.config.models.selection import SelectionConfig

ExtractionMode = Literal["llm", "embedding", "hybrid"]


class ContextExtractionConfig(BaseModel):
    """Context extraction step configuration."""

    enabled: bool = Field(default=True, description="Enable this step")
    mode: ExtractionMode = Field(default="llm", description="Extraction mode")
    llm_provider: str = Field(
        default="haiku",
        description="LLM provider for extraction",
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


class RuleFilteringConfig(BaseModel):
    """Rule filtering step configuration."""

    enabled: bool = Field(default=True, description="Enable this step")
    llm_provider: str = Field(
        default="haiku",
        description="LLM provider for filtering",
    )
    batch_size: int = Field(
        default=5,
        gt=0,
        description="Batch size for filtering",
    )


class ScenarioFilteringConfig(BaseModel):
    """Scenario filtering step configuration."""

    enabled: bool = Field(default=True, description="Enable this step")
    llm_provider: str = Field(
        default="haiku",
        description="LLM provider for scenario evaluation",
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


class GenerationConfig(BaseModel):
    """Response generation step configuration."""

    enabled: bool = Field(default=True, description="Enable this step")
    llm_provider: str = Field(
        default="sonnet",
        description="LLM provider for generation",
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


class EntityExtractionConfig(BaseModel):
    """Entity extraction configuration."""

    enabled: bool = Field(default=True, description="Enable entity extraction")
    llm_provider: str = Field(default="anthropic", description="LLM provider name")
    model: str = Field(default="haiku", description="Model to use")
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


class WindowSummarizationConfig(BaseModel):
    """Window summarization configuration."""

    turns_per_summary: int = Field(
        default=20, gt=0, description="Turns per summary window"
    )
    llm_provider: str = Field(default="anthropic", description="LLM provider")
    model: str = Field(default="haiku", description="Model to use")
    max_tokens: int = Field(default=256, gt=0, description="Max tokens")
    temperature: float = Field(default=0.5, ge=0.0, le=2.0, description="Temperature")


class MetaSummarizationConfig(BaseModel):
    """Meta-summarization configuration."""

    summaries_per_meta: int = Field(
        default=5, gt=0, description="Summaries per meta-summary"
    )
    enabled_at_turn_count: int = Field(
        default=100, gt=0, description="Enable meta-summaries at turn count"
    )
    llm_provider: str = Field(default="anthropic", description="LLM provider")
    model: str = Field(default="haiku", description="Model to use")
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

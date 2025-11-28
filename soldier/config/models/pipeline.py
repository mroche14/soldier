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


class LLMFilteringConfig(BaseModel):
    """LLM filtering step configuration."""

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
    llm_filtering: LLMFilteringConfig = Field(
        default_factory=LLMFilteringConfig,
        description="LLM filtering step",
    )
    generation: GenerationConfig = Field(
        default_factory=GenerationConfig,
        description="Response generation step",
    )
    enforcement: EnforcementConfig = Field(
        default_factory=EnforcementConfig,
        description="Enforcement step",
    )

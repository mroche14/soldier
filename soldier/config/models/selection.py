"""Selection strategy configuration models."""

from typing import Any, Literal

from pydantic import BaseModel, Field

SelectionStrategy = Literal["elbow", "adaptive_k", "entropy", "clustering", "fixed_k"]


class SelectionConfig(BaseModel):
    """Configuration for a selection strategy."""

    strategy: SelectionStrategy = Field(
        default="adaptive_k",
        description="Selection strategy",
    )
    min_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum score threshold",
    )
    max_k: int = Field(
        default=10,
        gt=0,
        description="Maximum items to select",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Strategy-specific parameters",
    )


class SelectionStrategiesConfig(BaseModel):
    """Configuration for selection strategies by content type."""

    rule: SelectionConfig = Field(
        default_factory=lambda: SelectionConfig(strategy="adaptive_k"),
        description="Rule selection strategy",
    )
    scenario: SelectionConfig = Field(
        default_factory=lambda: SelectionConfig(strategy="entropy"),
        description="Scenario selection strategy",
    )
    memory: SelectionConfig = Field(
        default_factory=lambda: SelectionConfig(strategy="clustering"),
        description="Memory selection strategy",
    )

"""Retrieval models for alignment pipeline.

Contains models for scored rules, scenarios, and retrieval results.
"""

from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from soldier.alignment.models import Rule


class RuleSource(str, Enum):
    """Source/scope of a retrieved rule."""

    GLOBAL = "global"  # Global scope
    SCENARIO = "scenario"  # Scenario-scoped
    STEP = "step"  # Step-scoped
    DIRECT = "direct"  # Directly referenced


class ScoredRule(BaseModel):
    """A rule with its retrieval score."""

    rule: Rule
    score: float = Field(ge=0.0, le=1.0, description="Similarity score")
    source: RuleSource = Field(default=RuleSource.GLOBAL, description="How it was retrieved")


class ScoredScenario(BaseModel):
    """A scenario with its retrieval score."""

    scenario_id: UUID
    scenario_name: str
    score: float = Field(ge=0.0, le=1.0, description="Similarity score")


class ScoredEpisode(BaseModel):
    """A memory episode with its retrieval score."""

    episode_id: UUID
    content: str
    score: float = Field(ge=0.0, le=1.0, description="Similarity score")
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalResult(BaseModel):
    """Result of the retrieval step."""

    rules: list[ScoredRule] = Field(default_factory=list)
    scenarios: list[ScoredScenario] = Field(default_factory=list)
    memory_episodes: list[ScoredEpisode] = Field(default_factory=list)

    # Metadata
    retrieval_time_ms: float = Field(default=0.0, ge=0)
    selection_metadata: dict[str, Any] = Field(
        default_factory=dict, description="Per-type selection info"
    )

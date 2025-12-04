"""Filtering models for alignment pipeline.

Contains models for rule and scenario filtering results.
"""

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from soldier.alignment.context.models import ScenarioSignal
from soldier.alignment.models import Rule


class MatchedRule(BaseModel):
    """A rule determined to apply to the current turn."""

    rule: Rule
    match_score: float = Field(ge=0.0, le=1.0, description="Original retrieval score")
    relevance_score: float = Field(ge=0.0, le=1.0, description="LLM-judged relevance")
    reasoning: str = Field(default="", description="Why it matches (for audit)")


class RuleFilterResult(BaseModel):
    """Result of rule filtering."""

    matched_rules: list[MatchedRule] = Field(default_factory=list)
    rejected_rule_ids: list[UUID] = Field(
        default_factory=list, description="IDs of rules that didn't match"
    )
    scenario_signal: ScenarioSignal | None = Field(default=None, description="Detected from rules")
    filter_time_ms: float = Field(default=0.0, ge=0)


class ScenarioAction(str, Enum):
    """Action to take regarding scenario navigation."""

    NONE = "none"  # No scenario action
    START = "start"  # Start a new scenario
    CONTINUE = "continue"  # Stay in current step
    TRANSITION = "transition"  # Move to new step
    EXIT = "exit"  # Exit scenario
    RELOCALIZE = "relocalize"  # Recovery to valid step


class ScenarioFilterResult(BaseModel):
    """Result of scenario filtering/navigation.

    Enhanced with profile requirements support (T156).
    """

    action: ScenarioAction
    scenario_id: UUID | None = None
    source_step_id: UUID | None = None
    target_step_id: UUID | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    reasoning: str = ""

    # For relocalization
    was_relocalized: bool = False
    original_step_id: UUID | None = None

    # Profile requirements (T156)
    missing_profile_fields: list[str] = Field(
        default_factory=list,
        description="Profile fields required but missing for this scenario",
    )
    blocked_by_missing_fields: bool = Field(
        default=False,
        description="True if scenario entry was blocked due to missing hard requirements",
    )

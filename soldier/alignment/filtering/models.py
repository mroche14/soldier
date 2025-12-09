"""Filtering models for alignment pipeline.

Contains models for rule and scenario filtering results.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, Field

from soldier.alignment.context.models import ScenarioSignal
from soldier.alignment.models import Rule

if TYPE_CHECKING:
    from soldier.alignment.retrieval.models import ScoredScenario
    from soldier.conversation.models.session import ScenarioInstance


class RuleApplicability(str, Enum):
    """LLM judgment of rule applicability (ternary output)."""

    APPLIES = "APPLIES"
    NOT_RELATED = "NOT_RELATED"
    UNSURE = "UNSURE"


class RuleEvaluation(BaseModel):
    """LLM evaluation of a single rule."""

    rule_id: UUID
    applicability: RuleApplicability
    confidence: float = Field(ge=0.0, le=1.0, description="LLM confidence in judgment")
    relevance: float = Field(ge=0.0, le=1.0, description="Relevance score")
    reasoning: str = Field(default="", description="Explanation")


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
    EXIT = "exit"  # Exit scenario (deprecated - use COMPLETE/CANCEL)
    RELOCALIZE = "relocalize"  # Recovery to valid step
    PAUSE = "pause"  # Temporarily pause scenario
    COMPLETE = "complete"  # Successfully complete scenario
    CANCEL = "cancel"  # Abort scenario without completion


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

    # Step skipping (P6.3)
    skipped_steps: list[UUID] = Field(
        default_factory=list,
        description="Steps skipped due to available data",
    )


class ScenarioLifecycleAction(str, Enum):
    """Lifecycle actions for scenarios."""

    START = "start"
    CONTINUE = "continue"
    PAUSE = "pause"
    COMPLETE = "complete"
    CANCEL = "cancel"


class ScenarioLifecycleDecision(BaseModel):
    """Decision about scenario lifecycle for this turn."""

    scenario_id: UUID
    action: ScenarioLifecycleAction
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)

    # Only for START
    entry_step_id: UUID | None = None

    # Only for PAUSE/COMPLETE/CANCEL
    source_step_id: UUID | None = None


class ScenarioStepTransitionDecision(BaseModel):
    """Decision about step transition within a scenario."""

    scenario_id: UUID
    source_step_id: UUID
    target_step_id: UUID
    was_skipped: bool = Field(default=False, description="True if steps were skipped")
    skipped_steps: list[UUID] = Field(
        default_factory=list, description="IDs of skipped steps"
    )
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)


class ScenarioSelectionContext(BaseModel):
    """Context for scenario lifecycle decisions."""

    candidates: list[ScoredScenario]
    active_instances: list[ScenarioInstance]
    applied_rules: list[Rule]

    # From SituationSnapshot (when Phase 2 implemented)
    canonical_intent: str | None = None
    intent_confidence: float | None = None

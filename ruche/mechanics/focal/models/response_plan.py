"""Response planning models.

Defines how scenarios contribute to response generation.
"""

from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ContributionType(str, Enum):
    """What the scenario wants to do this turn."""

    ASK = "ask"  # Ask a question
    INFORM = "inform"  # Provide information
    CONFIRM = "confirm"  # Confirm an action
    ACTION_HINT = "action_hint"  # Suggest tool execution
    NONE = "none"  # Silent this turn


class ScenarioContribution(BaseModel):
    """What a single scenario contributes to this turn."""

    scenario_id: UUID
    scenario_name: str
    current_step_id: UUID
    current_step_name: str
    contribution_type: ContributionType

    # For ASK: fields to collect
    fields_to_ask: list[str] = Field(default_factory=list)

    # For INFORM: template or guidance
    inform_template_id: UUID | None = None

    # For CONFIRM: action description
    action_to_confirm: str | None = None

    # For ACTION_HINT: tool suggestions
    suggested_tools: list[str] = Field(default_factory=list)

    # Priority for merging
    priority: int = Field(default=0, description="Higher priority wins conflicts")


class ScenarioContributionPlan(BaseModel):
    """Aggregated plan of what all scenarios want to contribute."""

    contributions: list[ScenarioContribution]
    primary_scenario_id: UUID | None = Field(
        default=None, description="Highest priority scenario"
    )
    has_asks: bool = Field(default=False, description="Any ASK contributions")
    has_confirms: bool = Field(default=False, description="Any CONFIRM contributions")
    has_action_hints: bool = Field(
        default=False, description="Any ACTION_HINT contributions"
    )

    @property
    def active_scenario_ids(self) -> list[UUID]:
        """Get list of active scenario IDs."""
        return [c.scenario_id for c in self.contributions]


class ResponseType(str, Enum):
    """Global response type for a turn."""

    ASK = "ASK"  # Asking for information
    ANSWER = "ANSWER"  # Providing information
    MIXED = "MIXED"  # Both asking and answering
    CONFIRM = "CONFIRM"  # Confirming an action
    REFUSE = "REFUSE"  # Refusing a request
    ESCALATE = "ESCALATE"  # Escalating to human/supervisor
    HANDOFF = "HANDOFF"  # Handoff to another system/channel


class RuleConstraint(BaseModel):
    """Pre-extracted constraint from a rule."""

    rule_id: str
    constraint_type: Literal["must_include", "must_avoid", "must_confirm"]
    text: str
    priority: int


class ResponsePlan(BaseModel):
    """Complete plan for generating a response."""

    global_response_type: ResponseType

    # Templates from scenario steps
    template_ids: list[str] = Field(default_factory=list)

    # High-level guidance
    bullet_points: list[str] = Field(default_factory=list)

    # Constraints from rules and scenarios
    must_include: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)

    # Per-scenario contributions (for debugging/analytics)
    scenario_contributions: dict[str, Any] = Field(default_factory=dict)

    # Pre-extracted rule constraints
    constraints_from_rules: list[RuleConstraint] = Field(default_factory=list)

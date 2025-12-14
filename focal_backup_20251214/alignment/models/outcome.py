"""Turn outcome models and categories.

Tracks the resolution and semantic categories for a turn.
"""

from enum import Enum

from pydantic import BaseModel, Field


class OutcomeCategory(str, Enum):
    """Semantic categories describing turn outcome.

    Categories are set by different pipeline phases:
    - PIPELINE categories: Set by Phases 7, 8, 10
    - GENERATION categories: Set by LLM in Phase 9
    """

    # Pipeline-set categories
    AWAITING_USER_INPUT = "AWAITING_USER_INPUT"  # Phase 8: Need info from user
    SYSTEM_ERROR = "SYSTEM_ERROR"  # Phase 7: Tool execution failed
    POLICY_RESTRICTION = "POLICY_RESTRICTION"  # Phase 10: Blocked by enforcement

    # LLM-set categories (from generation)
    KNOWLEDGE_GAP = "KNOWLEDGE_GAP"  # "I should know but don't"
    CAPABILITY_GAP = "CAPABILITY_GAP"  # "I can't do that action"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"  # "Not what this business handles"
    SAFETY_REFUSAL = "SAFETY_REFUSAL"  # "Refusing for safety"
    ANSWERED = "ANSWERED"  # Successfully answered


class TurnOutcome(BaseModel):
    """Final outcome of a turn with resolution and categories.

    Categories accumulate throughout the pipeline:
    - Phase 7 (Tool Execution): Appends SYSTEM_ERROR if tool failed
    - Phase 8 (Response Planning): Appends AWAITING_USER_INPUT if ASK mode
    - Phase 9 (Generation): LLM appends semantic categories
    - Phase 10 (Enforcement): Appends POLICY_RESTRICTION if blocked

    Resolution is determined in P9.5 based on categories and state.
    """

    resolution: str = Field(
        ...,
        description="Overall turn resolution: ANSWERED, PARTIAL, REDIRECTED, ERROR, BLOCKED",
    )
    categories: list[OutcomeCategory] = Field(
        default_factory=list,
        description="All semantic categories from pipeline and LLM",
    )

    # Additional metadata
    escalation_reason: str | None = Field(
        default=None,
        description="Reason if resolution is REDIRECTED",
    )
    blocking_rule_id: str | None = Field(
        default=None,
        description="Rule ID if resolution is BLOCKED",
    )

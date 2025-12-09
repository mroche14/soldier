"""TurnRecord model for audit domain."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from soldier.conversation.models.turn import ToolCall

if TYPE_CHECKING:
    from soldier.alignment.models.outcome import TurnOutcome


class TurnRecord(BaseModel):
    """Immutable audit record of a turn.

    This is a permanent audit copy of turn data that cannot
    be modified after creation.
    """

    model_config = ConfigDict(frozen=True)

    turn_id: UUID = Field(..., description="Turn identifier")
    tenant_id: UUID = Field(..., description="Owning tenant")
    agent_id: UUID = Field(..., description="Serving agent")
    session_id: UUID = Field(..., description="Parent session")
    turn_number: int = Field(..., description="Sequence number")
    user_message: str = Field(..., description="User input")
    agent_response: str = Field(..., description="Agent output")
    matched_rule_ids: list[UUID] = Field(
        default_factory=list, description="Rules matched"
    )
    scenario_id: UUID | None = Field(
        default=None, description="Active scenario"
    )
    step_id: UUID | None = Field(default=None, description="Active step")
    tool_calls: list[ToolCall] = Field(
        default_factory=list, description="Tools executed"
    )
    latency_ms: int = Field(..., description="Processing time")
    tokens_used: int = Field(..., description="Token consumption")
    timestamp: datetime = Field(..., description="Turn time")

    # Phase 11: Turn outcome tracking
    outcome: TurnOutcome | None = Field(
        default=None,
        description="Resolution status and categories"
    )

    # Phase decision fields (for debugging and analytics)
    canonical_intent: str | None = Field(
        default=None,
        description="Canonical intent label from Phase 2"
    )
    matched_rules_count: int = Field(
        default=0,
        description="Number of rules matched in Phase 5"
    )
    scenario_lifecycle_decisions: dict[str, str] = Field(
        default_factory=dict,
        description="Scenario ID → lifecycle action (CONTINUE, START, etc.)"
    )
    step_transitions: dict[str, dict] = Field(
        default_factory=dict,
        description="Scenario ID → {from_step, to_step, reason}"
    )
    tool_executions: list[dict] = Field(
        default_factory=list,
        description="Tools executed with results/errors"
    )
    enforcement_violations: list[str] = Field(
        default_factory=list,
        description="Constraint violations detected in Phase 10"
    )
    regeneration_attempts: int = Field(
        default=0,
        description="Number of regeneration attempts due to violations"
    )

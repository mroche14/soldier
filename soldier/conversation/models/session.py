"""Session models for conversation domain."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from soldier.conversation.models.enums import Channel, SessionStatus


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(UTC)


class StepVisit(BaseModel):
    """Record of visiting a scenario step."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    step_id: UUID = Field(..., description="Visited step")
    entered_at: datetime = Field(..., description="Entry time")
    turn_number: int = Field(..., description="Turn when entered")
    transition_reason: str | None = Field(
        default=None, description="How we got here"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Navigation confidence"
    )


class Session(BaseModel):
    """Runtime conversation state.

    Sessions track the current state of a conversation including
    scenario tracking, rule fires, variables, and customer profile link.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    session_id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    tenant_id: UUID = Field(..., description="Owning tenant")
    agent_id: UUID = Field(..., description="Serving agent")
    channel: Channel = Field(..., description="Communication channel")
    user_channel_id: str = Field(..., description="User identifier on channel")
    customer_profile_id: UUID | None = Field(
        default=None, description="Linked profile"
    )
    config_version: int = Field(..., description="Agent version in use")
    active_scenario_id: UUID | None = Field(
        default=None, description="Current scenario"
    )
    active_step_id: UUID | None = Field(
        default=None, description="Current step"
    )
    active_scenario_version: int | None = Field(
        default=None, description="Scenario version"
    )
    step_history: list[StepVisit] = Field(
        default_factory=list, description="Navigation history"
    )
    relocalization_count: int = Field(default=0, description="Recovery count")
    rule_fires: dict[str, int] = Field(
        default_factory=dict, description="rule_id -> fire count"
    )
    rule_last_fire_turn: dict[str, int] = Field(
        default_factory=dict, description="rule_id -> turn"
    )
    variables: dict[str, Any] = Field(
        default_factory=dict, description="Cached variable values"
    )
    variable_updated_at: dict[str, datetime] = Field(
        default_factory=dict, description="Variable timestamps"
    )
    turn_count: int = Field(default=0, description="Total turns")
    status: SessionStatus = Field(
        default=SessionStatus.ACTIVE, description="Current status"
    )
    created_at: datetime = Field(
        default_factory=utc_now, description="Creation time"
    )
    last_activity_at: datetime = Field(
        default_factory=utc_now, description="Last activity"
    )

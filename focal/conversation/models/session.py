"""Session models for conversation domain."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from focal.conversation.models.enums import Channel, SessionStatus


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(UTC)


class PendingMigration(BaseModel):
    """Session marker for pending migration."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    target_version: int = Field(..., description="Target scenario version")
    anchor_content_hash: str = Field(..., description="Anchor identifier")
    migration_plan_id: UUID = Field(..., description="Migration plan ID")
    marked_at: datetime = Field(
        default_factory=utc_now, description="When marked"
    )


class StepVisit(BaseModel):
    """Record of visiting a scenario step."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    step_id: UUID = Field(..., description="Visited step")
    step_name: str | None = Field(default=None, description="Step name for checkpoint description")
    entered_at: datetime = Field(..., description="Entry time")
    turn_number: int = Field(..., description="Turn when entered")
    transition_reason: str | None = Field(
        default=None, description="How we got here"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Navigation confidence"
    )
    is_checkpoint: bool = Field(
        default=False, description="Irreversible action step"
    )
    checkpoint_description: str | None = Field(
        default=None, description="Description if checkpoint"
    )
    step_content_hash: str | None = Field(
        default=None, description="For anchor matching"
    )


class ScenarioInstance(BaseModel):
    """Active scenario instance in a session.

    Tracks a single scenario's state within a multi-scenario session.
    Multiple scenarios can be active simultaneously.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    scenario_id: UUID = Field(..., description="Scenario being tracked")
    scenario_version: int = Field(..., description="Scenario version")
    current_step_id: UUID = Field(..., description="Current step in scenario")
    visited_steps: dict[UUID, int] = Field(
        default_factory=dict, description="step_id -> visit_count"
    )
    started_at: datetime = Field(
        default_factory=utc_now, description="When scenario started"
    )
    last_active_at: datetime = Field(
        default_factory=utc_now, description="Last activity timestamp"
    )
    paused_at: datetime | None = Field(
        default=None, description="When paused (if paused)"
    )
    variables: dict[str, Any] = Field(
        default_factory=dict, description="Scenario-scoped variables"
    )
    status: str = Field(
        default="active",
        description="Status: active, paused, completed, cancelled"
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

    # Multi-scenario support (Phase 6)
    active_scenarios: list[ScenarioInstance] = Field(
        default_factory=list, description="Currently active scenarios"
    )

    # Legacy single-scenario fields (deprecated - use active_scenarios)
    active_scenario_id: UUID | None = Field(
        default=None, description="Current scenario (deprecated)"
    )
    active_step_id: UUID | None = Field(
        default=None, description="Current step (deprecated)"
    )
    active_scenario_version: int | None = Field(
        default=None, description="Scenario version (deprecated)"
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
    pending_migration: PendingMigration | None = Field(
        default=None, description="Pending migration marker"
    )
    scenario_checksum: str | None = Field(
        default=None, description="For version validation"
    )
    created_at: datetime = Field(
        default_factory=utc_now, description="Creation time"
    )
    last_activity_at: datetime = Field(
        default_factory=utc_now, description="Last activity"
    )

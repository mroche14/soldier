"""Turn models for conversation domain."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(UTC)


class ToolCall(BaseModel):
    """Record of tool execution."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    tool_id: str = Field(..., description="Tool identifier")
    tool_name: str = Field(..., description="Human-readable name")
    input: dict[str, Any] = Field(..., description="Tool input")
    output: Any = Field(..., description="Tool output")
    success: bool = Field(..., description="Execution success")
    error: str | None = Field(default=None, description="Error message if failed")
    latency_ms: int = Field(..., description="Execution time")


class Turn(BaseModel):
    """Single conversation exchange.

    Represents one turn in a conversation with full metadata
    about processing, matching, and execution.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    turn_id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    tenant_id: UUID = Field(..., description="Owning tenant")
    session_id: UUID = Field(..., description="Parent session")
    turn_number: int = Field(..., description="Sequence number")
    user_message: str = Field(..., description="User input")
    agent_response: str = Field(..., description="Agent output")
    scenario_before: dict[str, str] | None = Field(
        default=None, description="State before turn"
    )
    scenario_after: dict[str, str] | None = Field(
        default=None, description="State after turn"
    )
    matched_rule_ids: list[UUID] = Field(
        default_factory=list, description="Rules that matched"
    )
    tool_calls: list[ToolCall] = Field(
        default_factory=list, description="Tools executed"
    )
    template_ids_used: list[UUID] = Field(
        default_factory=list, description="Templates used"
    )
    enforcement_triggered: bool = Field(
        default=False, description="Was enforcement needed"
    )
    enforcement_action: str | None = Field(
        default=None, description="What enforcement did"
    )
    latency_ms: int = Field(..., description="Processing time")
    tokens_used: int = Field(..., description="Token consumption")
    timestamp: datetime = Field(
        default_factory=utc_now, description="Turn time"
    )

"""TurnRecord model for audit domain."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from soldier.conversation.models.turn import ToolCall


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

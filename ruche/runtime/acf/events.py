"""Agent Conversation Fabric event types.

ACF emits events for observability, audit, and external integrations.
These are infrastructure events - not to be confused with AG-UI protocol
events (which are a channel adapter concern).
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(UTC)


class FabricEventType(str, Enum):
    """Event types emitted by ACF for observability and audit.

    These track ACF infrastructure operations, not user-facing events.
    """

    # Turn lifecycle
    TURN_STARTED = "turn_started"
    MESSAGE_ABSORBED = "message_absorbed"
    TURN_COMPLETED = "turn_completed"
    TURN_FAILED = "turn_failed"

    # Supersede coordination
    SUPERSEDE_REQUESTED = "supersede_requested"
    SUPERSEDE_EXECUTED = "supersede_executed"

    # Commit points
    COMMIT_POINT_REACHED = "commit_point_reached"

    # Tool execution (side effects)
    TOOL_AUTHORIZED = "tool_authorized"
    TOOL_EXECUTED = "tool_executed"

    # Session management
    SESSION_CREATED = "session_created"
    SESSION_RESUMED = "session_resumed"
    SESSION_CLOSED = "session_closed"

    # Mutex operations
    MUTEX_ACQUIRED = "mutex_acquired"
    MUTEX_RELEASED = "mutex_released"
    MUTEX_EXTENDED = "mutex_extended"


class FabricEvent(BaseModel):
    """Audit event emitted by ACF.

    Canonical event model for ACF observability. These events:
    - Track infrastructure operations
    - Enable audit trails
    - Support external integrations
    - Are NOT user-facing protocol events (that's channel adapter territory)
    """

    type: FabricEventType = Field(..., description="Event type (canonical field name)")
    logical_turn_id: UUID = Field(..., description="Associated turn")
    session_key: str = Field(..., description="Session identifier")
    timestamp: datetime = Field(default_factory=utc_now)
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Event-specific data"
    )

    # Optional routing context
    tenant_id: UUID | None = Field(default=None)
    agent_id: UUID | None = Field(default=None)
    interlocutor_id: UUID | None = Field(default=None)

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "type": "turn_started",
                "logical_turn_id": "123e4567-e89b-12d3-a456-426614174000",
                "session_key": "tenant:agent:customer:web",
                "timestamp": "2025-01-15T10:30:00Z",
                "payload": {"message_count": 1, "channel": "web"},
            }
        }

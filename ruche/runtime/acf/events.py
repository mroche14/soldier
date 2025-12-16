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


class ACFEventType(str, Enum):
    """Event types emitted by ACF for observability and audit.

    Event types use category.name format for better organization and filtering.
    Examples: 'turn.started', 'tool.executed', 'session.created'

    Categories:
    - turn: Turn lifecycle events
    - supersede: Turn superseding coordination
    - commit: Commit point tracking
    - tool: Tool execution events
    - enforcement: Constraint violations
    - session: Session management
    - mutex: Distributed lock operations
    """

    # Turn lifecycle
    TURN_STARTED = "turn.started"
    MESSAGE_ABSORBED = "turn.message_absorbed"
    TURN_COMPLETED = "turn.completed"
    TURN_FAILED = "turn.failed"

    # Supersede coordination
    SUPERSEDE_REQUESTED = "supersede.requested"
    SUPERSEDE_DECISION = "supersede.decision"
    SUPERSEDE_EXECUTED = "supersede.executed"

    # Commit points
    COMMIT_POINT_REACHED = "commit.reached"

    # Tool execution (side effects)
    TOOL_AUTHORIZED = "tool.authorized"
    TOOL_EXECUTED = "tool.executed"
    TOOL_FAILED = "tool.failed"

    # Enforcement
    ENFORCEMENT_VIOLATION = "enforcement.violation"

    # Session management
    SESSION_CREATED = "session.created"
    SESSION_RESUMED = "session.resumed"
    SESSION_CLOSED = "session.closed"

    # Mutex operations
    MUTEX_ACQUIRED = "mutex.acquired"
    MUTEX_RELEASED = "mutex.released"
    MUTEX_EXTENDED = "mutex.extended"


class ACFEvent(BaseModel):
    """Audit event emitted by ACF.

    Canonical event model for ACF observability. These events:
    - Track infrastructure operations
    - Enable audit trails
    - Support external integrations
    - Are NOT user-facing protocol events (that's channel adapter territory)

    Event types use category.name format for filtering and routing.
    Use category property to get category, event_name for the name,
    or matches_pattern() for flexible matching.
    """

    type: ACFEventType = Field(..., description="Event type (canonical field name)")
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

    @property
    def category(self) -> str:
        """Extract category from event type. Example: 'turn.started' → 'turn'"""
        return self.type.value.split(".")[0]

    @property
    def event_name(self) -> str:
        """Extract event name without category. Example: 'turn.started' → 'started'"""
        parts = self.type.value.split(".", 1)
        return parts[1] if len(parts) > 1 else parts[0]

    def matches_pattern(self, pattern: str) -> bool:
        """Check if event matches pattern. Supports '*', 'category.*', 'category.name'"""
        if pattern == "*":
            return True
        if pattern.endswith(".*"):
            return self.category == pattern[:-2]
        return self.type.value == pattern

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "type": "turn.started",
                "logical_turn_id": "123e4567-e89b-12d3-a456-426614174000",
                "session_key": "tenant:agent:customer:web",
                "timestamp": "2025-01-15T10:30:00Z",
                "payload": {"message_count": 1, "channel": "web"},
            }
        }


# Backward compatibility aliases (deprecated)
FabricEventType = ACFEventType
FabricEvent = ACFEvent

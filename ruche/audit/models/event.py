"""AuditEvent model for audit domain."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(UTC)


class AuditEvent(BaseModel):
    """Generic audit event.

    A flexible audit event type that can capture various
    system events for compliance and debugging.
    """

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    tenant_id: UUID = Field(..., description="Owning tenant")
    event_type: str = Field(..., description="Event classification")
    event_data: dict[str, Any] = Field(..., description="Event payload")
    session_id: UUID | None = Field(
        default=None, description="Related session"
    )
    turn_id: UUID | None = Field(default=None, description="Related turn")
    timestamp: datetime = Field(
        default_factory=utc_now, description="Event time"
    )

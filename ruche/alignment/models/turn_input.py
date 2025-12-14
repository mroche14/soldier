"""Turn input model.

Inbound event triggering a turn.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from ruche.conversation.models.enums import Channel


class TurnInput(BaseModel):
    """Inbound event triggering a turn.

    Parsed from API request in P1.1.
    """

    # Routing
    tenant_id: UUID = Field(..., description="Tenant ID")
    agent_id: UUID = Field(..., description="Agent ID")

    # Channel routing
    channel: Channel = Field(..., description="Communication channel")
    channel_user_id: str = Field(
        ..., description="Channel-specific user ID (phone, email, WhatsApp ID, etc.)"
    )

    # Optional direct identifiers
    customer_id: UUID | None = Field(
        default=None, description="Customer ID if already known"
    )
    session_id: UUID | None = Field(
        default=None, description="Session ID if already known"
    )

    # Message
    message: str = Field(..., description="User message content")
    message_id: str | None = Field(
        default=None, description="External message ID"
    )

    # Metadata
    language: str | None = Field(default=None, description="Message language code")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    # Timestamp
    received_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When message was received",
    )

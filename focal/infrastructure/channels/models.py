"""Channel data models.

Defines channel policies, bindings, and message formats.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ChannelType(str, Enum):
    """Supported channel types."""

    WEBCHAT = "webchat"  # AG-UI webchat
    SIMPLE_WEBCHAT = "simple_webchat"  # Plain WebSocket
    WHATSAPP = "whatsapp"  # Twilio WhatsApp
    EMAIL = "email"  # SMTP email
    SMS = "sms"  # Twilio SMS


class ChannelPolicy(BaseModel):
    """Policy for how a channel behaves.

    Defines rate limits, message formatting, and feature support.
    """

    channel_type: ChannelType = Field(..., description="Type of channel")

    # Rate limiting
    max_messages_per_minute: int | None = Field(
        None,
        description="Rate limit for outbound messages",
    )

    # Features
    supports_rich_text: bool = Field(default=False, description="HTML/Markdown support")
    supports_attachments: bool = Field(default=False, description="File attachments")
    supports_buttons: bool = Field(default=False, description="Interactive buttons")

    # Formatting
    max_message_length: int = Field(default=4096, description="Max message length")


class ChannelBinding(BaseModel):
    """Agent-channel binding.

    Links an agent to a channel with configuration.
    """

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID = Field(..., description="Tenant owning this binding")
    agent_id: UUID = Field(..., description="Agent bound to channel")
    channel_type: ChannelType = Field(..., description="Channel type")

    # Configuration
    enabled: bool = Field(default=True, description="Whether binding is active")
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Channel-specific configuration",
    )

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class InboundMessage(BaseModel):
    """Message received from a channel."""

    channel_type: ChannelType
    channel_user_id: str  # User identifier in channel's namespace
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class OutboundMessage(BaseModel):
    """Message to send via a channel."""

    channel_type: ChannelType
    channel_user_id: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)

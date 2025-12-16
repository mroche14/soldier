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


class SupersedeMode(str, Enum):
    """How to handle new messages during turn processing."""

    QUEUE = "queue"
    INTERRUPT = "interrupt"
    IGNORE = "ignore"


class ChannelPolicy(BaseModel):
    """Policy for how a channel behaves.

    Single source of truth for channel behavior.
    Used by ACF (accumulation), Agent (brain), and ChannelGateway (formatting).
    """

    channel: str = Field(..., description="Channel name (e.g., 'whatsapp', 'webchat')")

    # ACF Accumulation Behavior
    aggregation_window_ms: int = Field(
        default=3000,
        description="How long to wait for message bursts before processing",
    )
    supersede_default: SupersedeMode = Field(
        default=SupersedeMode.QUEUE,
        description="Default behavior when new message arrives during turn",
    )

    # ChannelAdapter Capabilities
    supports_typing_indicator: bool = Field(
        default=True,
        description="Whether channel supports typing indicators",
    )
    supports_read_receipts: bool = Field(
        default=True,
        description="Whether channel supports read receipts",
    )
    max_message_length: int | None = Field(
        default=None,
        description="Maximum characters per message (None = unlimited)",
    )
    supports_markdown: bool = Field(
        default=True,
        description="Whether channel renders markdown formatting",
    )
    supports_rich_media: bool = Field(
        default=True,
        description="Whether channel supports images, buttons, etc.",
    )

    # Agent/Brain Behavior
    natural_response_delay_ms: int = Field(
        default=0,
        description="Delay before sending response (to feel more natural)",
    )

    # Rate Limiting
    max_messages_per_minute: int = Field(
        default=60,
        description="Rate limit for outbound messages",
    )


class ChannelBinding(BaseModel):
    """Agent-channel binding.

    Maps a channel to agent configuration.
    Links an agent to a channel with configuration.
    """

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID = Field(..., description="Tenant owning this binding")
    agent_id: UUID = Field(..., description="Agent bound to channel")
    channel: str = Field(..., description="Channel name (e.g., 'whatsapp', 'webchat')")

    # Configuration
    enabled: bool = Field(default=True, description="Whether binding is active")
    webhook_url: str | None = Field(default=None, description="Webhook URL for this channel")
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

"""Channel policy models.

Defines policies for how agents behave on different channels.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SupersedeMode(str, Enum):
    """How to handle new messages while processing."""

    QUEUE = "queue"  # Queue new messages, process after current
    SUPERSEDE = "supersede"  # Abandon current, start new
    ASK_BRAIN = "ask_brain"  # Let brain decide


class ChannelPolicy(BaseModel):
    """Policy configuration for a communication channel.

    Defines behavior characteristics for how an agent interacts
    on a specific channel (e.g., WhatsApp, Slack, webchat).
    """

    channel: str = Field(..., description="Channel identifier")

    # Message accumulation
    aggregation_window_ms: int = Field(
        default=3000,
        description="How long to wait for additional messages before processing",
    )

    # Supersession handling
    supersede_default: SupersedeMode = Field(
        default=SupersedeMode.QUEUE,
        description="Default behavior when new message arrives during processing",
    )

    # Channel capabilities
    supports_typing_indicator: bool = Field(
        default=True,
        description="Whether channel supports typing indicators",
    )
    supports_read_receipts: bool = Field(
        default=True,
        description="Whether channel supports read receipts",
    )
    supports_markdown: bool = Field(
        default=True,
        description="Whether channel renders markdown",
    )
    supports_rich_media: bool = Field(
        default=True,
        description="Whether channel supports images, files, etc.",
    )

    # Limits
    max_message_length: int | None = Field(
        default=None,
        description="Maximum message length (None = no limit)",
    )
    max_messages_per_minute: int = Field(
        default=60,
        description="Rate limit for outbound messages",
    )

    # Response timing
    natural_response_delay_ms: int = Field(
        default=0,
        description="Artificial delay for more natural response timing",
    )


class ChannelBinding(BaseModel):
    """Binding of an agent to a channel with configuration."""

    channel: str = Field(..., description="Channel identifier")
    enabled: bool = Field(default=True, description="Whether binding is active")
    webhook_url: str | None = Field(
        default=None,
        description="Webhook URL for outbound messages",
    )
    credentials_ref: str | None = Field(
        default=None,
        description="Reference to channel credentials in secret store",
    )
    policy_overrides: dict[str, Any] = Field(
        default_factory=dict,
        description="Channel-specific policy overrides",
    )

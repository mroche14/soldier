"""Channel adapter protocol.

Defines the interface that all channel adapters must implement.
"""

from abc import abstractmethod
from typing import Protocol
from uuid import UUID

from ruche.runtime.channels.models import ChannelPolicy


class InboundMessage(Protocol):
    """Normalized inbound message from any channel.

    This is the canonical format that ChannelGateway produces
    and ACF/Agent consumes.
    """

    tenant_id: UUID
    agent_id: UUID
    channel: str
    channel_user_id: str
    content: str
    metadata: dict


class OutboundMessage(Protocol):
    """Outbound message from Agent to a channel."""

    tenant_id: UUID
    agent_id: UUID
    channel: str
    channel_user_id: str
    content: str
    metadata: dict


class DeliveryResult(Protocol):
    """Result of sending a message to a channel."""

    success: bool
    provider_message_id: str | None
    error_message: str | None


class ChannelAdapter(Protocol):
    """Protocol for channel integrations.

    Each channel (WhatsApp, SMS, webchat, etc.) implements this interface.
    Adapters handle channel-specific authentication, formatting, and delivery.
    """

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """Unique channel identifier: 'whatsapp', 'sms', 'email', 'webchat', etc."""
        ...

    @abstractmethod
    async def send_message(
        self,
        message: OutboundMessage,
        policy: ChannelPolicy,
    ) -> DeliveryResult:
        """Send message to channel.

        Args:
            message: Normalized outbound message
            policy: Channel policy with formatting rules

        Returns:
            DeliveryResult with provider message ID and status

        Raises:
            Exception: If delivery fails
        """
        ...

    @abstractmethod
    async def get_capabilities(self) -> ChannelPolicy:
        """Get channel capabilities and default policy.

        Returns:
            ChannelPolicy with channel-specific defaults
        """
        ...

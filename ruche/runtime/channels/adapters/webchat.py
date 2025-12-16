"""Webchat channel adapter.

Simple webchat adapter for embedded web widgets.
Supports markdown, rich media, and typing indicators.
"""

from typing import Any
from uuid import UUID

from ruche.observability.logging import get_logger
from ruche.runtime.channels.adapter import (
    ChannelAdapter,
    DeliveryResult,
    OutboundMessage,
)
from ruche.runtime.channels.models import ChannelPolicy

logger = get_logger(__name__)


class WebchatDeliveryResult:
    """Result of webchat message delivery."""

    def __init__(
        self,
        success: bool,
        provider_message_id: str | None = None,
        error_message: str | None = None,
    ):
        self.success = success
        self.provider_message_id = provider_message_id
        self.error_message = error_message


class WebchatAdapter(ChannelAdapter):
    """Webchat adapter for embedded web widgets.

    Supports:
    - Markdown formatting
    - Rich media (images, links)
    - Typing indicators
    - Read receipts
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize webchat adapter.

        Args:
            config: WebSocket or HTTP polling configuration
        """
        self._config = config or {}

    @property
    def channel_name(self) -> str:
        """Channel identifier."""
        return "webchat"

    async def send_message(
        self,
        message: OutboundMessage,
        policy: ChannelPolicy,
    ) -> DeliveryResult:
        """Send message via webchat.

        Args:
            message: Outbound message
            policy: Channel policy for formatting

        Returns:
            DeliveryResult with delivery status
        """
        try:
            # Format message according to policy
            formatted_content = self._format_message(message.content, policy)

            # Send via WebSocket or HTTP (stub implementation)
            message_id = await self._deliver(
                channel_user_id=message.channel_user_id,
                content=formatted_content,
                metadata=message.metadata,
            )

            logger.info(
                "webchat_message_sent",
                channel_user_id=message.channel_user_id,
                message_id=message_id,
                tenant_id=str(message.tenant_id),
                agent_id=str(message.agent_id),
            )

            return WebchatDeliveryResult(
                success=True,
                provider_message_id=message_id,
            )
        except Exception as e:
            logger.error(
                "webchat_delivery_failed",
                channel_user_id=message.channel_user_id,
                error=str(e),
            )
            return WebchatDeliveryResult(
                success=False,
                error_message=str(e),
            )

    async def get_capabilities(self) -> ChannelPolicy:
        """Get webchat capabilities.

        Returns:
            ChannelPolicy with webchat defaults
        """
        return ChannelPolicy(
            channel="webchat",
            aggregation_window_ms=600,
            supports_typing_indicator=True,
            supports_read_receipts=True,
            supports_markdown=True,
            supports_rich_media=True,
            max_message_length=10000,
            max_messages_per_minute=60,
            natural_response_delay_ms=500,
        )

    def _format_message(
        self,
        content: str,
        policy: ChannelPolicy,
    ) -> str:
        """Format message according to channel policy.

        Args:
            content: Raw message content
            policy: Channel policy

        Returns:
            Formatted content
        """
        formatted = content

        # Truncate if exceeds max length
        if policy.max_message_length and len(formatted) > policy.max_message_length:
            formatted = formatted[: policy.max_message_length - 3] + "..."

        return formatted

    async def _deliver(
        self,
        channel_user_id: str,
        content: str,
        metadata: dict[str, Any],
    ) -> str:
        """Deliver message to webchat user.

        This is a stub implementation. In production, this would:
        - Send via WebSocket connection
        - Or push to message queue for offline users
        - Or use HTTP polling endpoint

        Args:
            channel_user_id: User identifier
            content: Message content
            metadata: Additional metadata

        Returns:
            Provider message ID
        """
        # Stub: Would send via WebSocket or queue
        logger.debug(
            "webchat_deliver_stub",
            channel_user_id=channel_user_id,
            content_length=len(content),
        )

        # Return a synthetic message ID
        from uuid import uuid4

        return str(uuid4())
